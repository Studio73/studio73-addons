# -*- coding: utf-8 -*-
# (c) 2017 Studio73 - Pablo Fuentes <pablo@studio73>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import json
from datetime import datetime
from werkzeug import wrappers

from openerp import http, _
from openerp.http import request
from openerp.http import Controller
from openerp.addons.web.controllers.main import Session

LINE_TYPES = [
    'S1', 'S2', 'S3', 'S20', 'E21', 'E22', 'E23',
    'E24', 'E25', 'E99', 'N00', 'N01'
]
LINE_TAX_TYPES = [0, 4, 7, 8, 10, 16, 18, 21]
LINE_RE_TYPES = [0.5, 1.4, 1.75, 5.2]


class AccountInvoiceController(Controller):

    def _error(self, code, message):
        return {
            'result': 'error',
            'status': 400,
            'code': code,
            'message': message
        }

    @http.route(
        '/api/account.invoice/', type='json', methods=['POST'], auth='user'
    )
    def account_invoice_create(self, **kwargs):
        vals = {}

        # PARTNER
        if not kwargs.get('partner', False):
            return self._error(4100, _('Partner is missing'))

        partner = kwargs['partner']
        if not partner.get('vat', False):
            return self._error(4101, _('Partner VAT is missing'))
        if not partner.get('name', False):
            return self._error(4102, _('Partner name is missing'))
        if not partner.get('country_code', False):
            return self._error(4103, _('Partner country code is missing'))

        country = request.env['res.country'].search(
            [('code', '=', partner['country_code'])], limit=1)
        if not country:
            return self._error(4104, _('Country code is not allowed'))

        """
        # TODO ¿Que es esto?
        if not (account_rec or account_pay):
            return self._error(5101,
                               _('Company is not available to receive'
                                 ' invoices. Contact with the'
                                 ' IT support team'))
        """

        # INVOICE
        if not kwargs.get('date', False):
            vals['date_invoice'] = datetime.today().strftime('%Y-%m-%d')
        else:
            if self.check_date_type(kwargs['date']):
                vals['date_invoice'] = kwargs['date']
            else:
                return self._error(4205, _('Wrong date type'))

        # INVOICE TYPE
        if not kwargs.get('type', False):
            return self._error(4200, _('Invoice type is missing'))

        if kwargs['type'] not in ['out_invoice', 'out_refund',
                                  'in_invoice', 'in_refund']:
            return self._error(4201, _('Wrong invoice type'))

        vals['invoice_type'] = kwargs['type']

        if kwargs['type'] in ['in_invoice', 'in_refund']:
            if not kwargs.get('supplier_number', False):
                return self._error(
                    4202, _('Supplier invoice number is missing')
                )
            vals['supplier_invoice_number'] = kwargs['supplier_number']
            vals['reference'] = kwargs['supplier_number']

        # REGISTRATION KEY
        registration_key_code = kwargs.get('registration_key', '01')
        registration_key = request.env['aeat.sii.mapping.registration.keys']\
            .search(
            [('code', '=', registration_key_code)], limit=1
        )
        if not registration_key:
            return self._error(4203, _('Registration key is missing'))
        vals['registration_key'] = registration_key.id

        # THIRD PARTY
        if kwargs.get('third_party', False):
            if not kwargs.get('third_party_number', False):
                return self._error(4204, _('Third party number is missing'))

        vals.update({
            'third_party': kwargs.get('third_party', False),
            'third_party_number': kwargs.get('third_party_number', False),
        })

        if kwargs.get('number', False):
            vals.update({
                'number': kwargs['number'],
                'invoice_number': kwargs['number'],
            })

        if not kwargs.get('lines', False):
            return self._error(4300, _('Invoice lines are missing'))

        for line in kwargs['lines']:
            if not line.get('type', False):
                return self._error(4301, _('Invoice line type is missing'))
            if line['type'] not in LINE_TYPES:
                return self._error(4302, _('Wrong invoice line type'))
            if not line['base']:
                return self._error(4303, _('Invoice line base is missing'))

        vals["invoice_date"] = vals["date_invoice"]
        vals["name"] = partner["name"]
        vals["vat"] = partner["vat"]
        vals["country_id"] = country.id
        vals["type"] = vals["invoice_type"]
        # TODO
        vals["invoice_type"] = False
        # TODO
        vals["description"] = "Test"
        lines = kwargs["lines"]
        vals["base"] = sum(l.get("base", 0) for l in lines)
        vals["tax_amount"] = sum(l.get("tax_amount", 0) for l in lines)
        vals["line_ids"] = [(0, 0, l) for l in lines]

        invoice_import = request.env['account.invoice.import'].create(vals)
        """
        invoice = request.env['account.invoice'].create(vals)
        # TODO - Comprobar que esta agrupación es correcta
        if invoice.type in ['out_invoice', 'out_refund']:
            account_id = invoice.journal_id.default_debit_account_id.id
        else:
            account_id = invoice.journal_id.default_credit_account_id.id

        line_obj = request.env['account.invoice.line']
        # TODO - parsear bien los impuestos
        if kwargs['type'] in ['out_invoice', 'out_refund']:
            tax_code = 'S_IVA21B'
        else:
            tax_code = 'P_IVA21_BC'
        tax_id = request.env['account.tax'].search(
            [('description', '=', tax_code)], limit=1)

        for line in kwargs['lines']:
            line_obj.create({
                'invoice_id': invoice.id,
                'account_id': account_id,
                'name': '/',
                'price_unit': line['base'],
                'quantity': 1,
                'invoice_line_tax_id': [(4, [tax_id.id])]
            })
        """
        return {
            'result': invoice_import.id,
            'status': 200
        }

    def check_date_type(self, date):
        try:
            datetime.strptime(date)
        except Exception:
            try:
                datetime.strptime(date)
            except Exception:
                return False
        return True
