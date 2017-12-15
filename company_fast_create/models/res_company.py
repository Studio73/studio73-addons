# -*- coding: utf-8 -*-
# (c) 2017 Studio73 - Pablo Fuentes <pablo@studio73>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging
_logger = logging.getLogger(__name__)

from dateutil.relativedelta import relativedelta
from datetime import datetime

from openerp import models, fields, api

try:
    from openerp.addons.connector.queue.job import job
    from openerp.addons.connector.session import ConnectorSession
except ImportError:
    _logger.debug('Can not `import connector`.')
    import functools

    def empty_decorator_factory(*argv, **kwargs):
        return functools.partial
    job = empty_decorator_factory

class ResCompany(models.Model):
    _inherit = 'res.company'

    code_digits = fields.Integer(u'Dígitos del plan contable', default=6)

    @api.multi
    def fast_create(self):
        self.ensure_one()
        session = ConnectorSession.from_env(self.env)
        configure_company.delay(
            session, 'res.company', self.id, self.env.user.lang)
        return True

    def create_year_periods(self):
        """
        Se crea el año fiscal actual y el siguiente, siempre que no existan
        :return:
        """
        year_obj = self.env['account.fiscalyear']

        # Buscamos si ya existe el año fiscal actual
        today = datetime.today()
        exists = year_obj.search([('company_id', '=', self.id),
                                  ('code', '=', today.year)], limit=1)
        if not exists:
            date_start_now = datetime.strftime(today, "%Y-01-01")
            date_stop_now = datetime.strftime(today, "%Y-12-31")

            year_id = year_obj.create({'name': today.year,
                                       'code': today.year,
                                       'date_start': date_start_now,
                                       'date_stop': date_stop_now,
                                       'company_id': self.id,
                                       })
            year_id.create_period()

        # Buscamos si ya existe el año fiscal siguiente
        today_next = today + relativedelta(years=1)
        exists = year_obj.search([('company_id', '=', self.id),
                                  ('code', '=', today_next.year)], limit=1)
        if not exists:
            date_start_next = datetime.strftime(today_next, "%Y-01-01")
            date_stop_next = datetime.strftime(today_next, "%Y-12-31")

            year_id = year_obj.create({'name': today_next.year,
                                       'code': today_next.year,
                                       'date_start': date_start_next,
                                       'date_stop': date_stop_next,
                                       'company_id': self.id,
                                       })
            year_id.create_period()

        return True

    def create_journals(self):
        """
        Se crean los cuatro diarios básicos para poder crear facturas de todo
        tipo con Odoo
        :return:
        """
        journal_obj = self.env['account.journal']
        account_obj = self.env['account.account']

        # Diario de ventas
        exists = journal_obj.search([('company_id', '=', self.id),
                                     ('type', '=', 'sale')], limit=1)
        if not exists:
            account = account_obj.search(
                [('code', 'like', '700000')], limit=1)
            journal_obj.create({'name': 'Ventas',
                                'code': 'VENT',
                                'company_id': self.id,
                                'type': 'sale',
                                'update_posted': True,
                                'default_debit_account_id': account.id,
                                'default_credit_account_id': account.id})

        # Diario de abono de ventas
        exists = journal_obj.search([('company_id', '=', self.id),
                                     ('type', '=', 'sale_refund')], limit=1)
        if not exists:
            account = account_obj.search(
                [('code', 'like', '700000')], limit=1)
            journal_obj.create({'name': 'Abono de ventas',
                                'code': 'AVENT',
                                'company_id': self.id,
                                'type': 'sale_refund',
                                'update_posted': True,
                                'default_debit_account_id': account.id,
                                'default_credit_account_id': account.id})

        # Diario de compras
        exists = journal_obj.search([('company_id', '=', self.id),
                                     ('type', '=', 'purchase')], limit=1)
        if not exists:
            account = account_obj.search(
                [('code', 'like', '600000')], limit=1)
            journal_obj.create({'name': 'Compras',
                                'code': 'COMP',
                                'company_id': self.id,
                                'type': 'purchase',
                                'update_posted': True,
                                'default_debit_account_id': account.id,
                                'default_credit_account_id': account.id})

        # Diario de abono de compras
        exists = journal_obj.search([('company_id', '=', self.id),
                                     ('type', '=', 'purchase_refund')], limit=1)
        if not exists:
            account = account_obj.search(
                [('code', 'like', '600000')], limit=1)
            journal_obj.create({'name': 'Abono de compras',
                                'code': 'ACOM',
                                'company_id': self.id,
                                'type': 'purchase_refund',
                                'update_posted': True,
                                'default_debit_account_id': account.id,
                                'default_credit_account_id': account.id})

        return True

    def create_accounts_taxes(self):
        """
        Crea el wizard para actualizar el plan de cuentas y lo actualiza con el
        PGCE PYMEs 2008
        :return:
        """
        wizard_obj = self.env['wizard.update.charts.accounts']
        chart_template_id = self.env['account.chart.template']\
            .search([('name', '=', 'PGCE PYMEs 2008')], limit=1)

        data = {
            'company_id': self.id,
            'code_digits': self.code_digits or 6,
            'chart_template_id': chart_template_id.id,
        }

        wizard_id = wizard_obj.create(data)
        wizard_id.action_find_records()
        wizard_id.action_update_records()
        return True


@job(default_channel='root.configure_company')
def configure_company(session, model_name, company_id, lang):
    model = session.env[model_name]
    company = model.browse(company_id)
    company.create_year_periods()
    company.with_context({'lang': lang}).create_accounts_taxes()
    company.create_journals()
