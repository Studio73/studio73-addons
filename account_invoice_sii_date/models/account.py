# -*- coding: utf-8 -*-
# (c) 2017 Studio73 - Jordi Tolsa <jordi@studio73>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from openerp import models, fields, api


class AccountInvoice(models.Model):

    _inherit = 'account.invoice'

    sii_send_date = fields.Date(
        'Fecha envio SII',
        states={
            'paid': [('readonly', True)],
            'open': [('readonly', True)],
            'close': [('readonly', True)]
        },
        default=lambda *a: fields.Date.today(),
        select=True,
        copy=False)

    registration_date = fields.Date(
        u'Fecha de contabilización',
        states={
            'paid': [('readonly', True)],
            'open': [('readonly', True)],
            'close': [('readonly', True)]
        },
        select=True,
        default=lambda *a: fields.Date.today(),
        help="Keep empty to use the current date",
        copy=False,
    )

    def _get_account_registration_date(self):
        return self.sii_send_date or fields.Date.today()