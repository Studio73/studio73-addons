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
            invoice = account_invoice_obj.create({
                "partner_id": partner.id,
                "account_id": partner.property_account_receivable.id,
                "fiscal_position": partner.property_account_position and partner.property_account_position.id or False,
                "date_invoice": inv_import.invoice_date,
                "number": inv_import.number,
                "invoice_number": inv_import.number,
                "type": inv_import.type
            })

            if invoice.type in ['out_invoice', 'out_refund']:
                account_id = invoice.journal_id.default_debit_account_id.id
            else:
                account_id = invoice.journal_id.default_credit_account_id.id

            # TODO - parsear bien los impuestos
            if inv_import.type in ['out_invoice', 'out_refund']:
                tax_code = 'S_IVA21B'
            else:
                tax_code = 'P_IVA21_BC'

            tax_id = account_tax_obj.search([('description', '=', tax_code)], limit=1)

            for line in inv_import.line_ids:
                account_invoice_line_obj.create({
                    'invoice_id': invoice.id,
                    'account_id': account_id,
                    'name': '/',
                    'price_unit': line.base,
                    'quantity': 1,
                    'invoice_line_tax_id': [(4, [tax_id.id])]
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
            account_rec = account_account_obj.search([('code', 'like', '430000')], limit=1)
            account_pay = account_account_obj.search([('code', 'like', '410000')], limit=1)
            if not (account_rec or account_pay):
                raise Warning(_('Company is not available to receive invoices. Contact with the IT support team'))

            partner = res_partner_obj.create({
                'name': self.name,
                'vat': self.vat,
                'country_id': self.country_id.id,
                'property_account_receivable': account_rec.id,
                'property_account_payable': account_pay.id,
                'property_account_position': fposition.id,
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

        europe_group = self.env["res.country.group"].search([("name", "=", "Europe")], limit=1)
        europe = europe_group.mapped('country_ids.code')

        country = self.country_id
        # Conseguir la posicion fiscal en base al pais
        if country.code == 'ES':
            fposition = account_fiscal_pos_obj.search([('name', '=', u'Régimen Nacional')], limit=1)
        elif country.code in europe:
            fposition = account_fiscal_pos_obj.search([('name', '=', u'Régimen Intracomunitario')], limit=1)
        else:
            fposition = account_fiscal_pos_obj.search([('name', 'like', u'Régimen Extracomunitario')], limit=1)

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
        registration_key = self.env["aeat.sii.mapping.registration.keys"].search(domain)
        return registration_key and registration_key.id or False

    operation = fields.Selection(string="Operation", selection=[("A0", "A0 - Register new invoice"),
                                                                ("A1", "A1 - Modify existing invoice")], default="A0")
    name = fields.Char(string="Partner name", required=True)
    vat = fields.Char(string="Partner VAT", required=True)
    vat_type = fields.Selection(string="VAT type", selection=[('02', u'02 - NIF- VAT'),
                                                                    ('03', u'03 - Passport'),
                                                                    ('04', u'04 - Official id document'
                                                                           u' issued by the country'
                                                                           u' or territory of residence'),
                                                                    ('05', u'05 - Certificate of residence'),
                                                                    ('06', u'06 - Other documents'),
                                                                    ('07', u'07 - NO CENSUS')
                                                                    ], default="02")
    country_id = fields.Many2one("res.country", string="Country", required=True)
    type = fields.Selection(string="Type", required=True, selection=[('out_invoice', _('Issued invoice')),
                                                                     ('in_invoice', _('Received invoice')),
                                                                     ('out_refund', _('Rectified/amended issued invoice')),
                                                                     ('in_refund', _('Rectified/amended received invoice'))])
    number = fields.Char(string="Number", required=True)
    invoice_type = fields.Selection(string="Invoice type", selection=[("F1", u"Regular invoice"),
                                                                      ("F2", u"Simplified invoice (ticket)"),
                                                                      ("F3", u"Invoice replacing"
                                                                             u" simplified invoices"
                                                                             u" billed and declared"),
                                                                      ("F4", u"Record including a set of invoices"),
                                                                      ("F5", u"Import registers ( DUA)"),
                                                                      ("F6", u"Accounting records"),
                                                                      ("R1", u"Rectified/Amended invoice"
                                                                             u" (Error well founded"
                                                                             u" in law and Art. 80 "
                                                                             u"One Two and Six Spanish"
                                                                             u" VAT Act)"),
                                                                      ("R2", u"Rectified/Amended invoice (ART. 80.3 LIVA)"),
                                                                      ("R3", u"Rectified/Amended invoice (Art. 80.4 LIVA)"),
                                                                      ("R4", u"Rectified/Amended invoice (All cases)"),
                                                                      ("R5", u"Rectified/Amended Bill on simplified invoices")],
                                    default=_get_default_invoice_type)
    refund_type = fields.Selection(string="Refund type", selection=[("S", "S - Substitutes entirely the original invoice."),
                                                                    ("I", "I - Corrects the original invoice by adding/substracting the amounts on it to the original invoice amounts.")])
    rectified_invoices_number = fields.Char(string="Rectified invoices number")
    supplier_number = fields.Char(string="Supplier number")
    description = fields.Char(string="Operation description", required=True)
    invoice_date = fields.Date(string="Invoice date", required=True)
    transaction_date = fields.Date(string="Transaction date")
    record_date = fields.Date(string="Record date")
    period_id = fields.Many2one("account.period", string="Period")
    fiscalyear_id = fields.Many2one("account.fiscalyear", string="Year")
    registration_key_id = fields.Many2one("aeat.sii.mapping.registration.keys",
                                          string="Registration key",
                                          default=_get_default_registration_key)
    registration_key_id_code = fields.Char(related='registration_key_id.code',
                                           string="Registration key code")
    currency = fields.Char(string="Currency", default="EUR")
    third_party = fields.Boolean(string="Third party", default=False)
    third_party_number = fields.Char(string="Third party number")
    base = fields.Float(string="Base")
    tax_amount = fields.Float(string="Tax amount")
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
                                       ])
    base = fields.Float(string="Base")
    tax_type = fields.Float(string="Tax type")
    re_type = fields.Float(string="Surcharge type")
    tax_amount = fields.Float(string="Tax amount")
    re_amount = fields.Float(string="Surcharge amount")