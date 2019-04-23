# -*- coding: utf-8 -*-
# (c) 2017 Consultoría Informática Studio 73 S.L.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import datetime

from odoo import models, fields, api, _
from odoo.exceptions import Warning


class AccountInvoiceImport(models.Model):
    _inherit = ['mail.thread']
    _name = 'account.invoice.import'
    _order = 'number DESC'
    _description = 'Account invoice import'

    @api.model
    def create(self, vals):
        if vals.get('number', False):
            vals['number'] = vals['number'].rjust(4, '0')
        return super(AccountInvoiceImport, self).create(vals)

    @api.multi
    def write(self, vals):
        for inv_import in self:
            if inv_import.sii_state == 'not_sent' or not inv_import.sii_state:
                continue
            if 'invoice_date' in vals:
                raise Warning(
                    _("You cannot change the invoice date of an invoice "
                      "already registered at the SII. You must cancel the "
                      "invoice and create a new one with the correct date")
                )
        return super(AccountInvoiceImport, self).write(vals)

    @api.multi
    def cancel_sii(self):
        for inv_import in self.filtered(lambda i: i.invoice_id):
            invoice = inv_import.invoice_id
            invoice.cancel_sii()
        return True

    @api.multi
    def to_invoice_action_server(self):
        self.to_invoice()
        return {}

    @api.multi
    def to_invoice_force_company_user(self):
        """
        - Si queremos validar una importación de factura desde un usuario que
          pertenece a una compañía diferente a la compañía de la importación,
          para que no haya ningún problema de compañía al generar asientos,
          apuntes, etc...forzamos que la validación se haga con un usuario de
          la misma compañía que tiene asignada la importación
        """

        if self.env.user.company_id != self.company_id:
            company_user = self.env["res.users"].search(
                [("company_id", "=", self.company_id.id)], limit=1)
            self = self.sudo(company_user.id)

        self.to_invoice()

        return True

    @api.multi
    def to_invoice(self):

        account_invoice_obj = self.env["account.invoice"]
        account_invoice_line_obj = self.env['account.invoice.line']
        account_tax_obj = self.env["account.tax"]

        for inv_import in self:

            if not inv_import.line_ids:
                raise Warning(_("Please create some invoice lines"))

            partner = inv_import.get_partner()

            if inv_import.type in ['out_invoice', 'out_refund']:
                account_id = partner.property_account_receivable_id.id
            else:
                account_id = partner.property_account_payable_id.id

            invoice_vals = {
                "partner_id": partner.id,
                "account_id": account_id,
                "fiscal_position_id":
                    partner.property_account_position_id and
                    partner.property_account_position_id.id or False,
                "date": inv_import.date,
                "number": inv_import.number,
                "reference": inv_import.supplier_number or '',
                "invoice_number": inv_import.number,
                "type": inv_import.type,
                "company_id": inv_import.company_id.id,
                "currency_id": inv_import.currency_id.id,
                "sii_account_registration_date": inv_import.record_date,
                "sii_description": inv_import.description,
                "sii_registration_key": inv_import.registration_key_id.id,
            }

            if inv_import.invoice_type in ['F5']:
                invoice_vals['partner_id'] = inv_import.company_id.partner_id.id
                invoice_vals['fiscal_position_id'] = self.env['account.fiscal.position'].search([
                    ('name', '=', 'Importación con DUA'),
                    ('company_id', '=', inv_import.company_id.id)],
                    limit=1
                ).id

            invoice = inv_import.invoice_id
            if not invoice:
                invoice_vals.update({
                    "date_invoice": inv_import.invoice_date,
                })
                invoice = account_invoice_obj.create(invoice_vals)
            else:
                invoice.write(invoice_vals)

            if inv_import.type in ['out_invoice', 'out_refund']:
                account_line_id = partner.account_receivable_id \
                                  and partner.account_receivable_id.id \
                                  or False
                if not account_line_id:
                    account_line_id = \
                        invoice.journal_id.default_debit_account_id.id
            else:
                account_line_id = partner.account_payable_id \
                                  and partner.account_payable_id.id \
                                  or False
                if not account_line_id:
                    account_line_id = \
                        invoice.journal_id.default_credit_account_id.id

            for line in inv_import.line_ids:
                if inv_import.invoice_type in ['F5']:
                    product_comp_id = self.env['product.product'].search(
                        [('name', '=', 'DUA Compensación')], limit=1)
                    if line.type == 'E4':
                        product_iva_id = self.env['product.product'].search(
                            [('name', '=', 'E4')], limit=1)
                    else:
                        product_iva_id = self.env['product.product'].search(
                        [('name', 'ilike', 'DUA Valoración IVA 21')], limit=1)


                    invoice_line = line.invoice_line_id
                    if not invoice_line:
                        invoice_line = account_invoice_line_obj.create({
                            'invoice_id': invoice.id,
                            'account_id': account_line_id,
                            'name': inv_import.description,
                            'price_unit': line.base,
                            'quantity': 1,
                            'product_id': product_iva_id and product_iva_id.id or False,
                            'invoice_line_tax_ids': [(6, 0, product_iva_id.supplier_taxes_id.ids)]
                        })
                        line.invoice_line_id = invoice_line.id

                    invoice_line_aux = line.invoice_line_aux_id
                    if not invoice_line_aux:
                        invoice_line_aux = account_invoice_line_obj.create({
                            'invoice_id': invoice.id,
                            'account_id': account_line_id,
                            'name': inv_import.description,
                            'price_unit': line.base,
                            'quantity': -1,
                            'product_id': product_comp_id and product_comp_id.id or False,
                            'invoice_line_tax_ids': [(6, 0, product_comp_id.supplier_taxes_id.ids)]
                        })
                        line.invoice_line_aux_id = invoice_line_aux.id
                else:
                    tax_codes = []
                    product_id = False
                    if inv_import.type in ['out_invoice', 'out_refund']:
                        if line.type == 'S1':
                            if line.tax_type in ['21', '10', '4', '0']:
                                tax_codes.append('S_IVA%sB' % line.tax_type)
                            else:
                                raise Warning(
                                    _('The tax type of the lines is not supported.'
                                      ' Contact with the IT support team')
                                )
                        elif line.type == 'S2':
                            tax_codes.append('S_IVA0_ISP')
                        elif line.type == 'E5':
                            tax_codes.append('S_IVA0_IC')
                        elif line.type == 'E4':
                            tax_codes.append('S_IVA0')
                            product_id = self.env['product.product'].search(
                                [('name', '=', 'E4')], limit=1)
                    else:
                        if line.type == 'S1':
                            if line.tax_type in ['21', '10', '4', '0']:
                                tax_codes.append('P_IVA%s_BC' % line.tax_type)
                            else:
                                raise Warning(
                                    _('The tax type of the lines is not supported.'
                                      ' Contact with the IT support team')
                                )
                        elif line.type == 'S2':
                            partner_fposition = \
                                partner.property_account_position_id \
                                and partner.property_account_position_id.name or ''
                            if partner_fposition == u'Régimen Nacional':
                                if line.tax_type in ['21', '10', '4']:
                                    tax_codes.append('P_IVA%s_ISP_1'
                                                     % line.tax_type)
                                else:
                                    raise Warning(
                                        _(
                                            'The tax type of the lines is not '
                                            'supported. Contact with the IT '
                                            'support team')
                                    )
                            elif partner_fposition == u'Régimen Intracomunitario':
                                if line.tax_type in ['21', '10', '4']:
                                    tax_codes.append('P_IVA%s_SP_IN_1'
                                                     % line.tax_type)
                                else:
                                    raise Warning(
                                        _(
                                            'The tax type of the lines is not '
                                            'supported. Contact with the IT '
                                            'support team')
                                    )
                            elif partner_fposition == u'Régimen Extracomunitario':
                                if line.tax_type in ['21', '10', '4']:
                                    tax_codes.append('P_IVA%s_SP_EX_1'
                                                     % line.tax_type)
                                else:
                                    raise Warning(
                                        _(
                                            'The tax type of the lines is not '
                                            'supported. Contact with the IT '
                                            'support team')
                                    )

                        elif line.type == 'E5':
                            tax_codes.append('P_IVA0_BC')
                        elif line.type == 'E4':
                            tax_codes.append('P_IVA0_BC')
                            product_id = self.env['product.product'].search(
                                [('name', '=', 'E4')], limit=1)

                    tax_ids = self.env["account.tax"]
                    for tax_code in tax_codes:
                        tax_id = account_tax_obj.search([
                            ('description', '=', tax_code),
                            ('company_id', '=', invoice.company_id.id)
                        ], limit=1)
                        tax_ids += tax_id

                    fpos = invoice.fiscal_position_id
                    fp_taxes = fpos.map_tax(tax_ids)

                    invoice_line = line.invoice_line_id
                    if not invoice_line:
                        invoice_line = account_invoice_line_obj.create({
                            'invoice_id': invoice.id,
                            'account_id': account_line_id,
                            'name': inv_import.description,
                            'price_unit': line.base,
                            'quantity': 1,
                            'product_id': product_id and product_id.id or False,
                            'invoice_line_tax_ids': [(6, 0, fp_taxes.ids)]
                        })
                        line.invoice_line_id = invoice_line.id

            if not inv_import.invoice_id:
                inv_import.invoice_id = invoice.id

            invoice.compute_taxes()
            invoice.action_invoice_open()
            inv_import.state = "validated"

        return True

    @api.multi
    def to_draft(self):
        """
        - Si se vuelve a borrador una factura ya enviada al SII, en vez de
          intentar borrar la factura se debe quedar en borrador a la espera
          de que se cambien datos y se valide de nuevo.
            - En caso de que no haya sido enviada, borramos la factura
            - Si ha sido enviada, la dejamos en borrador y borramos
              unicamente las lineas
        """
        for inv_import in self:
            invoice = inv_import.invoice_id
            if invoice:
                if not invoice.sii_state or invoice.sii_state not in \
                        ["sent", "sent_w_errors", "sent_modified"]:
                    invoice.action_invoice_cancel()
                    invoice.internal_number = False
                    invoice.move_name = False
                    invoice.unlink()
                else:
                    invoice.action_invoice_cancel()
                    invoice.action_invoice_draft()
                    invoice.internal_number = False
                    invoice.state = "draft"
                    invoice.invoice_line_ids.unlink()
            inv_import.state = "draft"
        return True

    @api.multi
    def get_partner(self):
        self.ensure_one()
        if self.vat == self.company_id.vat and not self.invoice_type == 'F5':
            raise Warning(
                _('ERROR: The VAT-Id number can\'t'
                  ' be the same of the company.')
            )

        res_partner_obj = self.env["res.partner"]
        account_account_obj = self.env["account.account"]

        partner = self.partner_id
        if not partner:
            if self.vat:
                partner = res_partner_obj.search(
                    [('vat', '=', self.vat)], limit=1)
                if not partner:
                    partner = res_partner_obj.search(
                        [('vat', 'ilike', self.vat)], limit=1)
        fposition = self.get_fposition()

        account_rec = account_account_obj.search([
            ('code', 'like', '430.'),
            ('company_id', '=', self.company_id.id)
        ], limit=1)
        account_pay = account_account_obj.search([
            ('code', 'like', '410.'),
            ('company_id', '=', self.company_id.id)
        ], limit=1)

        if not (account_rec or account_pay):
            raise Warning(
                _('Company is not available to receive invoices.'
                  ' Contact with the IT support team')
            )

        if not partner:

            country_code = self.country_id.code
            if country_code == "GR":
                country_code = "EL"

            if country_code in self.vat:
                vat = self.vat
            else:
                vat = "%s%s" % (country_code, self.vat)

            partner = res_partner_obj.create({
                'name': self.name,
                'vat': vat,
                'country_id': self.country_id.id,
                'property_account_receivable_id': account_rec.id,
                'property_account_payable_id': account_pay.id,
                'property_account_position_id': fposition.id,
                'type': 'other',
                'customer': True if
                self.type in ['out_invoice', 'out_refund'] else False,
                'supplier': True if
                self.type in ['in_invoice', 'in_refund'] else False,
            })
            self.partner_id = partner
        else:
            if not self.partner_id and partner:
                self.partner_id = partner
            if partner.country_id != self.country_id:
                partner.country_id = self.country_id.id
            if partner.name != self.name:
                partner.name = self.name
            if partner.property_account_position_id != fposition:
                partner.property_account_position_id = fposition.id
            if not partner.property_account_receivable_id:
                partner.property_account_receivable_id = account_rec.id
            if not partner.property_account_payable_id:
                partner.property_account_payable_id = account_pay.id

        return partner

    @api.multi
    def get_fposition(self):
        self.ensure_one()

        account_fiscal_pos_obj = self.env["account.fiscal.position"]

        europe_group = \
            self.env["res.country.group"].search([("name", "=", "Europe")],
                                                 limit=1)
        europe = europe_group.mapped('country_ids.code')

        country = self.country_id
        # Conseguir la posicion fiscal en base al pais
        if country.code == 'ES':
            fposition = account_fiscal_pos_obj.search([
                ('name', '=', u'Régimen Nacional'),
                ('company_id', '=', self.company_id.id)
            ], limit=1)
        elif country.code in europe:
            fposition = account_fiscal_pos_obj.search([
                ('name', '=', u'Régimen Intracomunitario'),
                ('company_id', '=', self.company_id.id)
            ], limit=1)
        else:
            fposition = account_fiscal_pos_obj.search([
                ('name', 'like', u'Régimen Extracomunitario'),
                ('company_id', '=', self.company_id.id)
            ], limit=1)

        return fposition

    def _get_default_invoice_type(self):
        type = self._context.get("type", False)
        return type and "F1" if \
            type in ["out_invoice", "in_invoice"] else "R4" or None

    def _get_default_registration_key(self):
        type = self._context.get("type", False)
        domain = [("code", "=", "01")]
        if type in ["out_invoice", "out_refund"]:
            domain.append(("type", "=", "sale"))
        else:
            domain.append(("type", "=", "purchase"))

        registration_key = self.env[
            "aeat.sii.mapping.registration.keys"].search(domain)
        return registration_key or None

    def _get_default_currency(self):
        currency = self.env["res.currency"].search(
            [("name", "=", "EUR")], limit=1)
        return currency and currency.id or None

    def _get_default_company(self):
        return self.env["res.users"]._get_company() or None

    operation = fields.Selection(
        string="Operation",
        selection=[
            ("A0", "A0 - Register new invoice"),
            ("A1", "A1 - Modify existing invoice")
        ],
        default="A0"
    )
    partner_id = fields.Many2one(comodel_name="res.partner", string="Partner")
    name = fields.Char(
        string="Partner",
        required=True,
        track_visibility='always'
    )
    vat = fields.Char(string="Recipient’s VAT-Id number", required=True)
    vat_type = fields.Selection(
        string="Recipient’s VAT-Id Type",
        selection=[('02', u'02 - NIF- VAT'),
                   ('03', u'03 - Passport'),
                   ('04', u'04 - Official id document issued '
                          u'by the country or territory of residence'),
                   ('05', u'05 - Certificate of residence'),
                   ('06', u'06 - Other documents'),
                   ('07', u'07 - NO CENSUS')],
        default="02",
        required=True
    )
    country_id = fields.Many2one(
        comodel_name="res.country",
        string="Recipient’s country",
        required=True
    )
    type = fields.Selection(
        string="Type",
        required=True,
        selection=[('out_invoice', _('Issued invoice')),
                   ('in_invoice', _('Received invoice')),
                   ('out_refund', _('Rectified/amended issued invoice')),
                   ('in_refund', _('Rectified/amended received invoice'))],
        track_visibility='always'
    )
    number = fields.Char(
        string="Invoice number",
        copy=False,
    )
    invoice_type = fields.Selection(
        string="Invoice type",
        selection=[
            ("F1", u"F1 - Regular invoice"),
            ("F2", u"F2 - Simplified invoice (ticket)"),
            ("F3", u"F3 - Invoice replacing simplified invoices billed"
                   u" and declared"),
            ("F4", u"F4 - Record including a set of invoices"),
            ("F5", u"F5 - Import registers ( DUA)"),
            ("F6", u"F6 - Accounting records"),
            ("R1", u"R1 - Rectified/Amended invoice (Error well founded "
                   u"in law and Art. 80 One Two and Six Spanish VAT Act)"),
            ("R2", u"R2 - Rectified/Amended invoice (ART. 80.3 LIVA)"),
            ("R3", u"R3 - Rectified/Amended invoice (Art. 80.4 LIVA)"),
            ("R4", u"R4 - Rectified/Amended invoice (All cases)"),
            ("R5", u"R5 - Rectified/Amended Bill on simplified invoices")
        ],
        default=_get_default_invoice_type,
        required=True
    )
    refund_type = fields.Selection(
        string="Refund type",
        selection=[
            ("S", "S - Substitutes entirely the original invoice."),
            ("I", "I - Corrects the original invoice by adding/substracting "
                  "the amounts on it to the original invoice amounts.")
        ]
    )
    rectified_invoices_number = fields.Char(
        string="Number(s) of the invoice(s) rectified"
    )
    supplier_number = fields.Char(
        string="Supplier’s invoice number",
        copy=False,
    )
    description = fields.Char(string="Operation description", required=True)
    invoice_date = fields.Date(
        string="Invoice date",
        copy=False
    )
    date = fields.Date(
        string='Accounting Date',
        copy=False,
        help="Keep empty to use the invoice date.",
        required=True,
        default=lambda *a: datetime.now().strftime('%Y-%m-%d')
    )
    transaction_date = fields.Date(string="Transaction date")
    record_date = fields.Date(string="Record date")
    registration_key_id = fields.Many2one(
        comodel_name="aeat.sii.mapping.registration.keys",
        string="Registration key",
        default=_get_default_registration_key,
        required=True
    )
    registration_key_id_code = fields.Char(
        related='registration_key_id.code',
        string="Registration key code"
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Currency",
        default=_get_default_currency,
        track_visibility='always'
    )
    third_party = fields.Boolean(string="Third party", default=False)
    third_party_number = fields.Char(string="Third party number")
    base = fields.Float(
        string="Base",
        store=True,
        compute="_calculate_amount",
        track_visibility='always'
    )
    tax_amount = fields.Float(
        string="Tax amount",
        store=True,
        compute="_calculate_amount",
        track_visibility='always'
    )
    line_ids = fields.One2many(
        comodel_name="account.invoice.import.line",
        inverse_name="invoice_import_id",
        string="Lines",
        required=True
    )
    payment_date = fields.Date(string="Payment date")
    payment_amount = fields.Float(string="Payment amount")
    collection_payment_method = fields.Selection(
        string="Collection payment method",
        selection=[
            ("01", "01 - Transfer"),
            ("02", "02 - Check"),
            ("03", "03 - Waived / pay (deadline accrual / "
                   "forced accrual in bankruptcy)"),
            ("04", "04 - Other means receivable / payable")
        ]
    )
    bank_account = fields.Char(string="IBAN")
    realproperty_location = fields.Selection(
        string="Real property location",
        selection=[
            ("1", u"1 - Real property with cadastral code located within "
                  u"the Spanish territory except Basque Country and Navarra"),
            ("2", u"2 - Real property located in the Basque "
                  u"Country or Navarra"),
            ("3", u"3 - Real property in any of the above situations "
                  u"but without cadastral code."),
            ("4", u"4 - Real property located in a foreign country.")
        ]
    )
    realproperty_cadastrial_code = fields.Char(
        string="Real property cadastrial code"
    )
    state = fields.Selection(
        string="State",
        selection=[
            ("draft", "Draft"),
            ("validated", "Validated")
        ],
        default="draft",
        track_visibility='onchange'
    )
    invoice_id = fields.Many2one(
        comodel_name="account.invoice",
        string="Invoice",
        copy=False
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        default=_get_default_company
    )
    sii_state = fields.Selection(
        string="SII send state",
        readonly=True,
        copy=False,
        help="Indicates the state of this invoice in relation"
             " with the presentation at the SII",
        related="invoice_id.sii_state",
        store=True
    )
    sii_csv = fields.Char(
        string='SII CSV',
        copy=False,
        readonly=True,
        related="invoice_id.sii_csv",
        store=True
    )
    invoice_jobs_ids = fields.Many2many(
        comodel_name='queue.job',
        column1='invoice_id',
        column2='job_id',
        string="Connector Jobs",
        copy=False,
        related="invoice_id.invoice_jobs_ids",
        relation="account_invoice_jobs_rel",
        store=True
    )
    sii_header_sent = fields.Text(
        string="SII last header sent",
        copy=False,
        readonly=True,
        related="invoice_id.sii_header_sent",
        store=True
    )
    sii_content_sent = fields.Text(
        string="SII last content sent",
        copy=False,
        readonly=True,
        related="invoice_id.sii_content_sent",
        store=True
    )
    sii_return = fields.Text(
        string='SII Return',
        copy=False,
        readonly=True,
        related="invoice_id.sii_return",
        store=True
    )
    delivery_in_progress = fields.Boolean(string="Delivery in progress")
    intracommunity_operation = fields.Boolean(
        string="Intracommunity Operation",
        compute="_compute_intracommunity_operation"
    )
    down_payment = fields.Boolean(string="Down payment")
    dispatch_goods = fields.Boolean(string="Dispatch of goods")

    @api.multi
    def _compute_intracommunity_operation(self):
        europe_country_group = self.env["res.country.group"].search(
            [("name", "ilike", "europe")], limit=1)
        if not europe_country_group:
            return
        for inv in self.filtered(lambda i: i.country_id):
            flag = False
            if inv.country_id.id in europe_country_group.country_ids.ids:
                flag = True
            inv.intracommunity_operation = flag

    @api.onchange("invoice_date")
    def onchange_invoice_date(self):
        invoice_date = self.invoice_date
        self.transaction_date = invoice_date
        self.record_date = invoice_date
        self.date = invoice_date

    @api.multi
    @api.depends("line_ids", "line_ids.base", "line_ids.tax_amount")
    def _calculate_amount(self):
        for imp in self:
            self.base = sum(l.base for l in imp.line_ids)
            self.tax_amount = sum(l.tax_amount for l in imp.line_ids)

    @api.multi
    def unlink(self):
        if self.state == 'validated':
            raise Warning(_("You cannot delete a validated invoice."))
        elif self.sii_state and self.sii_state != 'not_sent':
            raise Warning(_("You cannot delete a invoice sent to SII."))
        return super(AccountInvoiceImport, self).unlink()

    @api.onchange('dispatch_goods')
    def onchage_dispatch_goods(self):
        res = {}
        if self.dispatch_goods:
            res = {
                'warning': {
                    'title': _('Warning'),
                    'message': _('Remember to fill the transaction date '
                                 'field with the transport start date.')
                }
            }
        if res:
            return res

    @api.onchange('down_payment')
    def onchage_down_payment(self):
        res = {}
        if self.down_payment:
            res = {
                'warning': {
                    'title': _('Warning'),
                    'message': _('Remember to upload the payment document.')
                }
            }
        if res:
            return res

    @api.onchange("vat")
    def onchange_vat(self):
        partner_id = False
        if self.vat:
            partner_id = self.env['res.partner'].search(
                [('vat', '=', self.vat)], limit=1)
            if not partner_id:
                partner_id = self.env['res.partner'].search(
                    [('vat', 'ilike', self.vat)], limit=1)
        self.vat = partner_id and partner_id.vat or self.vat
        self.partner_id = partner_id
        self.name = partner_id and partner_id.name or False
        self.country_id = partner_id and partner_id.country_id or False


class AccountInvoiceImportLine(models.Model):
    _name = "account.invoice.import.line"
    _description = 'Account invoice import line'

    invoice_import_id = fields.Many2one(
        comodel_name="account.invoice.import",
        string="Import invoice",
        ondelete="cascade"
    )
    invoice_line_id = fields.Many2one(
        comodel_name="account.invoice.line",
        string="Invoice line"
    )
    invoice_line_aux_id = fields.Many2one(
        comodel_name="account.invoice.line",
        string="Invoice line aux"
    )
    type = fields.Selection(
        string="Type",
        selection=[
            ("S1", u"S1 - No Exempt – No reverse charge mechanism"),
            ("S2", u"S2 - No exempt – reverse charge mechanism"),
            ("S3", u"S3 - No exempt – Reverse/No reverse charge mechanism"),
            ("E1", u"E1 - Exempt according to Article 20 of VAT Act"
                   u" (Technical exemptions)"),
            ("E2", u"E2 - Exempt according to Article 21 of VAT Act"
                   u" (Technical exemptions)"),
            ("E3", u"E3 - Exempt according to Article 22 of VAT Act"
                   u" (Technical exemptions)"),
            ("E4", u"E4 - Exempt according to Article 23 and 24 of VAT Act"
                   u" (Customs VAT schemes)"),
            ("E5", u"E5 - Exempt according to Article 25 of VAT Act"
                   u" (Intra-Community supplies)"),
            ("E6", u"E6 - Exempt others encompassing E1 to E6.")
        ],
        default="S1",
        required=True
    )
    base = fields.Float(string="Base")
    tax_type = fields.Selection(
        string="Tax type",
        selection=[
            ("0", '0%'),
            ("4", '4%'),
            ("7", '7%'),
            ("8", '8%'),
            ("10", '10%'),
            ("16", '16%'),
            ("18", '18%'),
            ("21", '21%')
        ],
        default="21",
        required=True
    )
    re_type = fields.Selection(
        string="Surcharge type",
        selection=[
            ("0", '0%'),
            ("0.5", '0.5%'),
            ("1.4", '1.4%'),
            ("1.75", '1.75%'),
            ("5.2", '5.2%')
        ]
    )
    tax_amount = fields.Float(
        string="Tax amount",
        store=True,
        compute="_calculate_tax_amount"
    )
    re_amount = fields.Float(
        string="Surcharge amount",
        store=True,
        compute="_calculate_re_amount"
    )

    @api.multi
    @api.depends("base", "tax_type")
    def _calculate_tax_amount(self):
        for line in self:
            line.tax_amount = line.base * (
                    (
                            (line.tax_type and float(line.tax_type)) / 100
                    ) or 0
            )

    @api.multi
    @api.depends("base", "re_type")
    def _calculate_re_amount(self):
        for line in self:
            line.re_amount = line.base * (
                    (
                            (line.re_type and float(line.re_type)) / 100
                    ) or 0
            )


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    @api.multi
    def _compute_dua_invoice(self):
        for invoice in self:
            if invoice.fiscal_position_id.name == u'Importación con DUA' and \
                    invoice.tax_line_ids.\
                    filtered(lambda x: x.tax_id.description in
                             ['P_IVA21_IBC', 'P_IVA10_IBC', 'P_IVA4_IBC',
                              'P_IVA21_IBI', 'P_IVA10_IBI', 'P_IVA4_IBI',
                              'P_IVA21_SP_EX', 'P_IVA10_SP_EX',
                              'P_IVA4_SP_EX','P_IVA0_BC']):
                invoice.sii_dua_invoice = True
            else:
                invoice.sii_dua_invoice = False

    sii_dua_invoice = fields.Boolean("SII DUA Invoice",
                                     compute="_compute_dua_invoice")
