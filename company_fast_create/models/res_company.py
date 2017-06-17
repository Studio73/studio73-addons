# -*- coding: utf-8 -*-
# (c) 2017 Studio73 - Pablo Fuentes <pablo@studio73>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from openerp import models, fields, api


class ResCompany(models.Model):
    _inherit = 'res.company'

    @api.multi
    def fast_create(self):
        self.ensure_one()
        self.create_journals()
        self.create_year_periods()
        self.create_accounts_taxes()
        return True

    def create_journals(self):
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

    def create_year_periods(self):
        year_obj = self.env['account.fiscalyear']

        # Buscamos si ya existe el año fiscal
        exists = year_obj.search([('company_id', '=', self.id),
                                  ('code', '=', '2017'),
                                  ('name', '=', '2017')], limit=1)
        if not exists:
            # TODO - Crear el año fiscal respecto a la fecha actual
            year_id = year_obj.create({'name': '2017',
                                       'code': '2017',
                                       'date_start': '01/01/2017',
                                       'date_stop': '31/12/2017',
                                       'company_id': self.id,
                                       })
            year_id.create_period()
        return True

    def create_accounts_taxes(self):
        return True

