# -*- coding: utf-8 -*-
# (c) 2017 Consultoría Informática Studio 73 S.L.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from openerp import models, fields, api, _
from openerp.exceptions import Warning


class AccountInvoiceImport(models.Model):
    _name = 'account.invoice.import'

    @api.multi
    def to_invoice(self):
        account_invoice_obj = self.env["account.invoice"]
        account_invoice_line_obj = self.env['account.invoice.line']
        account_tax_obj = self.env["account.tax"]

        for inv_import in self:
            partner = inv_import.get_partner()
            if inv_import.type in ['out_invoice', 'out_refund']:
                account_id = partner.property_account_receivable.id
            else:
                account_id = partner.property_account_payable.id

            invoice = account_invoice_obj.create({
                "partner_id": partner.id,
                "account_id": account_id,
                "fiscal_position": partner.property_account_position and
                partner.property_account_position.id or False,
                "date_invoice": inv_import.invoice_date,
                "sii_send_date": inv_import.record_date,
                "registration_date": inv_import.period_id.date_stop,
                "period_id": inv_import.period_id.id,
                "number": inv_import.number,
                "supplier_invoice_number": inv_import.supplier_number or '',
                "invoice_number": inv_import.number,
                "type": inv_import.type,
                "sii_description": inv_import.description,
                "sii_registration_key": inv_import.registration_key_id.id,
                "company_id": inv_import.company_id.id,
                "currency_id": inv_import.currency_id.id
            })
            if inv_import.type in ['out_invoice', 'out_refund']:
                account_line_id = \
                    invoice.journal_id.default_debit_account_id.id
            else:
                account_line_id = \
                    invoice.journal_id.default_credit_account_id.id

            for line in inv_import.line_ids:
                # TODO - parsear bien los impuestos
                tax_codes = []
                product_id = False
                if inv_import.type in ['out_invoice', 'out_refund']:
                    if line.type == 'S1':
                        tax_codes.append('S_IVA21B')
                    elif line.type == 'S2':
                        tax_codes.append('S_IVA0_ISP')
                    elif line.type == 'E5':
                        tax_codes.append('S_IVA0_IC')
                    elif line.type == 'E4':
                        tax_codes.append('S_IVA0')
                        product_id = self.env['product.product'].search([
                            ('name', '=', 'E4')],
                            limit=1)
                else:
                    tax_codes.append('P_IVA21_BC')

                tax_ids = self.env["account.tax"]
                for tax_code in tax_codes:
                    tax_id = account_tax_obj.search([
                        ('description', '=', tax_code),
                        ('company_id', '=', invoice.company_id.id)
                    ],
                        limit=1)
                    tax_ids += tax_id
                fpos = invoice.fiscal_position
                fp_taxes = fpos.map_tax(tax_ids)

                account_invoice_line_obj.create({
                    'invoice_id': invoice.id,
                    'account_id': account_line_id,
                    'name': '/',
                    'price_unit': line.base,
                    'quantity': 1,
                    'product_id': product_id and product_id.id or False,
                    'invoice_line_tax_id': [(6, 0, fp_taxes.ids)]
                })

            inv_import.invoice_id = invoice.id
            inv_import.state = "validated"
            invoice.action_date_assign()
            invoice.action_move_create()
            invoice.action_number()
            invoice.invoice_validate()

        return True

    @api.multi
    def to_draft(self):
        for inv_import in self:
            invoice = inv_import.invoice_id
            if invoice:
                invoice.action_cancel()
                invoice.internal_number = False
                invoice.unlink()
            inv_import.state = "draft"
        return True

    @api.multi
    def get_partner(self):
        self.ensure_one()

        res_partner_obj = self.env["res.partner"]
        account_account_obj = self.env["account.account"]

        partner = res_partner_obj.search([("vat", "=", self.vat)], limit=1)
        fposition = self.get_fposition()

        if not partner:
            account_rec = \
                account_account_obj.search([('code', 'like', '430000')],
                                           limit=1)
            account_pay = \
                account_account_obj.search([('code', 'like', '410000')],
                                           limit=1)
            if not (account_rec or account_pay):
                raise Warning(_('Company is not available to receive invoices.'
                                ' Contact with the IT support team'))
            if self.country_id.code in self.vat:
                vat = self.vat
            else:
                vat = "%s%s" % (self.country_id.code, self.vat)
            partner = res_partner_obj.create({
                'name': self.name,
                'vat': vat,
                'country_id': self.country_id.id,
                'property_account_receivable': account_rec.id,
                'property_account_payable': account_pay.id,
                'property_account_position': fposition.id,
                'type': 'default',
            })
        else:
            if partner.country_id != self.country_id:
                partner.country_id = self.country_id
            if partner.name != partner['name']:
                partner.name = partner['name']
            if partner.property_account_position != fposition:
                partner.property_account_position = fposition.id

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
            fposition = account_fiscal_pos_obj.search(
                [('name', '=', u'Régimen Nacional')], limit=1)
        elif country.code in europe:
            fposition = account_fiscal_pos_obj.search(
                [('name', '=', u'Régimen Intracomunitario')], limit=1)
        else:
            fposition = account_fiscal_pos_obj.search(
                [('name', 'like', u'Régimen Extracomunitario')], limit=1)

        return fposition

    def _get_default_invoice_type(self):
        type = self._context.get("type", False)
        return type and "F1" if type in ["out_invoice", "in_invoice"]\
            else "R4" or False

    def _get_default_registration_key(self):
        type = self._context.get("type", False)
        domain = [("code", "=", "01")]
        if type in ["out_invoice", "out_refund"]:
            domain.append(("type", "=", "sale"))
        else:
            domain.append(("type", "=", "purchase"))
        registration_key = \
            self.env["aeat.sii.mapping.registration.keys"].search(domain)
        return registration_key or False

    def _get_default_currency(self):
        currency = self.env["res.currency"].search([("name", "=", "EUR")])
        return currency or False

    def _get_default_company(self):
        company_id = self.env["res.users"]._get_company()
        return company_id and self.env["res.company"].browse(company_id) or False

    operation = fields.Selection(string="Operation", selection=[("A0", "A0 - Register new invoice"),
                                                                ("A1", "A1 - Modify existing invoice")], default="A0")
    name = fields.Char(string="Invoice recipient name", required=True)
    vat = fields.Char(string="Recipient’s VAT-Id number", required=True)
    vat_type = fields.Selection(string="Recipient’s VAT-Id Type", selection=[('02', u'02 - NIF- VAT'),
                                                                             ('03', u'03 - Passport'),
                                                                             ('04', u'04 - Official id document'
                                                                                    u' issued by the country'
                                                                                    u' or territory of residence'),
                                                                             ('05', u'05 - Certificate of residence'),
                                                                             ('06', u'06 - Other documents'),
                                                                             ('07', u'07 - NO CENSUS')
                                                                             ], default="02", required=True)
    country_id = fields.Many2one("res.country", string="Recipient’s country", required=True)
    type = fields.Selection(string="Type", required=True, selection=[('out_invoice', _('Issued invoice')),
                                                                     ('in_invoice', _('Received invoice')),
                                                                     ('out_refund', _('Rectified/amended issued invoice')),
                                                                     ('in_refund', _('Rectified/amended received invoice'))])
    number = fields.Char(string="Invoice number", required=True)
    invoice_type = fields.Selection(string="Invoice type", selection=[("F1", u"F1 - Regular invoice"),
                                                                      ("F2", u"F2 - Simplified invoice (ticket)"),
                                                                      ("F3", u"F3 - Invoice replacing"
                                                                             u" simplified invoices"
                                                                             u" billed and declared"),
                                                                      ("F4", u"F4 - Record including a set of invoices"),
                                                                      ("F5", u"F5 - Import registers ( DUA)"),
                                                                      ("F6", u"F6 - Accounting records"),
                                                                      ("R1", u"R1 - Rectified/Amended invoice"
                                                                             u" (Error well founded"
                                                                             u" in law and Art. 80 "
                                                                             u"One Two and Six Spanish"
                                                                             u" VAT Act)"),
                                                                      ("R2", u"R2 - Rectified/Amended invoice (ART. 80.3 LIVA)"),
                                                                      ("R3", u"R3 - Rectified/Amended invoice (Art. 80.4 LIVA)"),
                                                                      ("R4", u"R4 - Rectified/Amended invoice (All cases)"),
                                                                      ("R5", u"R5 - Rectified/Amended Bill on simplified invoices")],
                                    default=_get_default_invoice_type, required=True)
    refund_type = fields.Selection(string="Refund type", selection=[("S", "S - Substitutes entirely the original invoice."),
                                                                    ("I", "I - Corrects the original invoice by adding/substracting the amounts on it to the original invoice amounts.")])
    rectified_invoices_number = fields.Char(string="Number(s) of the invoice(s) rectified")
    supplier_number = fields.Char(string="Supplier’s invoice number")
    description = fields.Char(string="Operation description", required=True)
    invoice_date = fields.Date(string="Invoice date", required=True)
    transaction_date = fields.Date(string="Transaction date")
    record_date = fields.Date(string="Record date")
    period_id = fields.Many2one("account.period", string="Period")
    fiscalyear_id = fields.Many2one("account.fiscalyear", string="Year")
    registration_key_id = fields.Many2one("aeat.sii.mapping.registration.keys",
                                          string="Registration key",
                                          default=_get_default_registration_key,
                                          required=True)
    registration_key_id_code = fields.Char(related='registration_key_id.code',
                                           string="Registration key code")
    currency_id = fields.Many2one("res.currency", string="Currency", default=_get_default_currency)
    third_party = fields.Boolean(string="Third party", default=False)
    third_party_number = fields.Char(string="Third party number")
    base = fields.Float(string="Base", store=True, compute="_calculate_amount")
    tax_amount = fields.Float(string="Tax amount", store=True, compute="_calculate_amount")
    line_ids = fields.One2many(comodel_name="account.invoice.import.line", inverse_name="invoice_import_id",
                                    string="Lines", required=True)
    payment_date = fields.Date(string="Payment date")
    payment_amount = fields.Float(string="Payment amount")
    collection_payment_method = fields.Selection(string="Collection payment method",
                                                 selection=[("01", "01 - Transfer"),
                                                            ("02", "02 - Check"),
                                                            ("03", "03 - Waived / pay (deadline accrual / forced accrual in bankruptcy)"),
                                                            ("04", "04 - Other means receivable / payable")])
    bank_account = fields.Char(string="IBAN")
    realproperty_location = fields.Selection(string="Real property location",
                                             selection=[("1", u"1 - Real property with cadastral code located within the Spanish territory except Basque Country and Navarra"),
                                                        ("2", u"2 - Real property located in the Basque Country or Navarra"),
                                                        ("3", u"3 - Real property in any of the above situations but without cadastral code."),
                                                        ("4", u"4 - Real property located in a foreign country.")])
    realproperty_cadastrial_code = fields.Char(string="Real property cadastrial code")
    state = fields.Selection(string="State", selection=[("draft", "Draft"),
                                                        ("validated", "Validated")], default="draft")
    invoice_id = fields.Many2one("account.invoice", string="Invoice")
    company_id = fields.Many2one("res.company", string="Company", required=True, default=_get_default_company)

    @api.onchange("invoice_date")
    def onchange_invoice_date(self):
        invoice_date = self.invoice_date
        self.transaction_date = invoice_date
        self.record_date = invoice_date

    @api.onchange("record_date")
    def onchange_record_date(self):
        if self.record_date:
            period = self.env["account.period"].find(dt=self.record_date)
            if period:
                self.period_id = period.id
                self.fiscalyear_id = period.fiscalyear_id.id

    @api.multi
    @api.depends("line_ids", "line_ids.base", "line_ids.tax_amount")
    def _calculate_amount(self):
        for imp in self:
            self.base = sum(l.base for l in imp.line_ids)
            self.tax_amount = sum(l.tax_amount for l in imp.line_ids)


class AccountInvoiceImportLine(models.Model):
    _name = "account.invoice.import.line"

    invoice_import_id = fields.Many2one("account.invoice.import", string="Import invoice")
    type = fields.Selection(string="Type",
                            selection=[("S1", u"S1 - No Exempt – No reverse charge mechanism"),
                                       ("S2", u"S2 - No exempt – reverse charge mechanism"),
                                       ("S3", u"S3 - No exempt – Reverse/No reverse charge mechanism"),
                                       ("E1", u"E1 - Exempt according to Article 20 of VAT Act (Technical exemptions)"),
                                       ("E2", u"E2 - Exempt according to Article 21 of VAT Act (Technical exemptions)"),
                                       ("E3", u"E3 - Exempt according to Article 22 of VAT Act (Technical exemptions)"),
                                       ("E4", u"E4 - Exempt according to Article 23 and 24 of VAT Act (Customs VAT schemes)"),
                                       ("E5", u"E5 - Exempt according to Article 25 of VAT Act (Intra-Community supplies)"),
                                       ("E6", u"E6 - Exempt others encompassing E1 to E6."),
                                       # ("N0", u"N0 - No sujeta, si la sujeción es por el art. 7, 14, otros"),
                                       # ("N1", u"No sujeta, si la sujeción es por operaciones no sujetas en el TAI por reglas de localización")
                                       ], default="S1", required=True)
    base = fields.Float(string="Base")
    tax_type = fields.Selection(string="Tax type", selection=[("0", '0%'),
                                                              ("4", '4%'),
                                                              ("7", '7%'),
                                                              ("8", '8%'),
                                                              ("10", '10%'),
                                                              ("16", '16%'),
                                                              ("18", '18%'),
                                                              ("21", '21%')],
                                default="21", required=True)
    re_type = fields.Selection(string="Surcharge type",
                               selection=[("0", '0%'),
                                          ("0.5", '0.5%'),
                                          ("1.4", '1.4%'),
                                          ("1.75", '1.75%'),
                                          ("5.2", '5.2%')])
    tax_amount = fields.Float(string="Tax amount", store=True, compute="_calculate_tax_amount")
    re_amount = fields.Float(string="Surcharge amount", store=True, compute="_calculate_re_amount")

    @api.multi
    @api.depends("base", "tax_type")
    def _calculate_tax_amount(self):
        for line in self:
            line.tax_amount = line.base * (((line.tax_type and float(line.tax_type)) / 100) or 0)

    @api.multi
    @api.depends("base", "re_type")
    def _calculate_re_amount(self):
        for line in self:
            line.re_amount = line.base * (((line.re_type and float(line.re_type)) / 100) or 0)
