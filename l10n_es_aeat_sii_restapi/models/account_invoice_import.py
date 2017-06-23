# -*- coding: utf-8 -*-
# (c) 2017 Consultoría Informática Studio 73 S.L.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from openerp import models, fields, api, _


class AccountInvoiceImport(models.Model):
    _name = 'account.invoice.import'

    def _get_default_invoice_type(self):
        type = self._context.get("type", False)
        return type and "F1" if type in ["out_invoice", "in_invoice"] else "R4" or False

    def _get_default_registration_key(self):
        type = self._context.get("type", False)
        domain = [("code", "=", "01")]
        if type in ["out_invoice", "out_refund"]:
            domain.append(("type", "=", "sale"))
        else:
            domain.append(("type", "=", "purchase"))
        registration_key = self.env["aeat.sii.mapping.registration.keys"].search(domain)
        return registration_key and registration_key.id or False

    operation = fields.Selection(string="Operation", selection=[("A0", "A0"),
                                                                ("A1", "A1")], default="A0")
    name = fields.Char(string="Partner name", required=True)
    vat = fields.Char(string="Partner VAT", required=True)
    vat_type = fields.Selection(string="VAT type", selection=[('02', u'2 - NIF-IVA'),
                                                                    ('03', u'3 - PASAPORTE'),
                                                                    ('04', u'4 - DOCUMENTO OFICIAL DE IDENTIFICACIÓN '
                                                                           u'EXPEDIDO POR EL PAIS O TERRITORIO DE '
                                                                           u'RESIDENCIA'),
                                                                    ('05', u'5 - CERTIFICADO DE RESIDENCIA'),
                                                                    ('06', u'6 - OTRO DOCUMENTO PROBATORIO'),
                                                                    ('07', u'7 - NO CENSADO')
                                                                    ], default="02")
    country_id = fields.Many2one("res.country", string="Country", required=True)
    type = fields.Selection(string="Type", required=True, selection=[('out_invoice', _('Invoice')),
                                                                     ('in_invoice', _('Supplier Invoice')),
                                                                     ('out_refund', _('Refund')),
                                                                     ('in_refund', _('Supplier Refund'))])
    number = fields.Char(string="Number", required=True)
    invoice_type = fields.Selection(string="Invoice type", selection=[("F1", u"Factura normal"),
                                                                      ("F2", u"Factura simplificada (ticket)"),
                                                                      ("F3", u"Factura emitida en sustitución de facturas"
                                                                             u"simplificadas facturadas y declaradas"),
                                                                      ("F4", u"Asiento resumen de facturas"),
                                                                      ("F5", u"Importaciones (DUA)"),
                                                                      ("F6", u"Justificantes contables"),
                                                                      ("R1", u"Factura rectificativa (Error fundado en "
                                                                             u"derecho y Art. 80 Uno Dos y Seis LIVA)"),
                                                                      ("R2", u"Factura rectificativa (Art. 80.3 LIVA)"),
                                                                      ("R3", u"Factura rectificativa (Art. 80.4 LIVA)"),
                                                                      ("R4", u"Factura rectificativa (Resto)"),
                                                                      ("R5", u"Factura rectificativa en facturas "
                                                                             u"simplificadas")],
                                    default=_get_default_invoice_type)
    refund_type = fields.Selection(string="Refund type", selection=[("S", "Factura sustitutiva"),
                                                                    ("I", "Rectificativa por diferencia")])
    rectified_invoices_number = fields.Char(string="Rectified invoices number")
    supplier_number = fields.Char(string="Supplier number")
    description = fields.Char(string="Operation description", required=True)
    invoice_date = fields.Date(string="Invoice date", required=True)
    transaction_date = fields.Date(string="Transaction date")
    record_date = fields.Date(string="Record date")
    period_id = fields.Many2one("account.period", string="Period")
    fiscalyear_id = fields.Many2one("account.fiscalyear", string="Year")
    registration_key_id = fields.Many2one("aeat.sii.mapping.registration.keys", string="Registration key",
                                          default=_get_default_registration_key)
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
                                                 selection=[("01", "Transferencia"),
                                                            ("02", "Cheque"),
                                                            ("03", "No se cobra / paga (fecha límite de devengo / "
                                                                   "devengo forzoso en concurso de acreedores)"),
                                                            ("04", "Otros medios de cobro / pago")])
    bank_account = fields.Char(string="IBAN")
    realproperty_location = fields.Selection(string="Real property location",
                                             selection=[("1", u"Inmueble con referencia catastral situado en cualquier "
                                                              u"punto del territorio español, excepto País Vasco y "
                                                              u"Navarra"),
                                                        ("2", u"Inmueble situado en la Comunidad Autónoma del País Vasco"
                                                              u" o en la Comunidad Foral de Navarra"),
                                                        ("3", u"Inmueble en cualquiera de las situaciones anteriores "
                                                              u"pero sin referencia catastral"),
                                                        ("4", u"Inmueble situado en el extranjero")])
    realproperty_cadastrial_code = fields.Char(string="Real property cadastrial code")


class AccountInvoiceImportLine(models.Model):
    _name = "account.invoice.import.line"

    invoice_import_id = fields.Many2one("account.invoice.import", string="Import invoice")
    type = fields.Selection(string="Type",
                            selection=[("S1", u"No exenta- Sin inversión sujeto pasivo"),
                                       ("S2", u"No exenta - Con inversión sujeto pasivo"),
                                       ("E1", u"Exenta por el artículo 20"),
                                       ("E2", u"Exenta por el artículo 21"),
                                       ("E3", u"Exenta por el artículo 22"),
                                       ("E4", u"Exenta por artículo 23 y 24"),
                                       ("E5", u"Exenta por el artículo 25"),
                                       ("E6", u"Exenta por Otros"),
                                       ("N0", u"No sujeta, si la sujeción es por el art. 7, 14, otros"),
                                       ("N1", u"No sujeta, si la sujeción es por operaciones no sujetas en el TAI por"
                                              u" reglas de localización")])
    base = fields.Float(string="Base")
    tax_type = fields.Float(string="Tax type")
    re_type = fields.Float(string="Surcharge type")
    tax_amount = fields.Float(string="Tax amount")
    re_amount = fields.Float(string="Surcharge amount")