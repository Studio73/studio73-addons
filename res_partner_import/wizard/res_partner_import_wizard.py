# -*- coding: utf-8 -*-
# (c) 2017 Consultoría Informática Studio 73 S.L.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import openpyxl
from tempfile import TemporaryFile

from odoo import models, fields, api, _
from odoo.exceptions import Warning


class ResPartnerImportWizard(models.TransientModel):
    _name = 'res.partner.import.wizard'

    file = fields.Binary(string="File to import")
    filename = fields.Char(string="Filename")

    @api.multi
    def import_xlsx(self):
        if not self.file:
            raise Warning(_(u"You must select the file with the partners to import"))

        sheets = self.get_excel_sheets(self.file.decode('base64'))
        partners = self.parse_sheet(sheets[0])
        self.import_partners(partners)
        return True

    @api.multi
    def import_partners(self, partners):
        """

        :param data:
        :return:
        """
        account_account_obj = self.env["account.account"]
        res_partner_obj = self.env["res.partner"]
        res_better_zip_obj = self.env["res.better.zip"]

        for partner_vals in partners:
            account_code = str(partner_vals["account_code"]).strip()
            account = account_account_obj.search([("code", "=", account_code)])
            if not account:
                raise Warning(
                    _(u"You can not import the company '%s' because the account "
                      u"'%s' has not been found" % (partner_vals["name"], account_code))
                )
            partner_vals.pop("account_code", None)

            partner_vals.update({
                "company_type": "company"
            })

            domain = []
            if account_code.startswith("43"):
                partner_vals.update({
                    "customer": True,
                    "property_account_receivable_id": account.id,
                    "customer_seq": account_code,
                })
                domain = [("customer", "=", True), ("customer_seq", "=", account_code)]
            elif account_code.startswith("40"):
                partner_vals.update({
                    "customer": False,
                    "supplier": True,
                    "property_account_payable_id": account.id,
                    "supplier_seq": account_code,
                })
                domain = [("supplier", "=", True), ("supplier_seq", "=", account_code)]
            elif account_code.startswith("41"):
                partner_vals.update({
                    "customer": False,
                    "supplier": True,
                    "creditor": True,
                    "property_account_payable_id": account.id,
                    "supplier_seq": account_code,
                })
                domain = [("supplier", "=", True), ("creditor", "=", True), ("supplier_seq", "=", account_code)]

            if not domain:
                raise Warning(
                    _(u"Check the partner '%s' because the account is not one that starts "
                      u"with '40', '41' or '43'" % partner_vals["name"])
                )

            zip = partner_vals["zip"]
            if zip:
                better_zip = res_better_zip_obj.search([("name", "=", zip)], limit=1)
                if better_zip:
                    partner_vals.update({
                        "city": better_zip.city,
                        "zip_id": better_zip.id,
                        "country_id": better_zip.country_id.id,
                        "state_id": better_zip.state_id.id,
                    })
                    country_id_code = better_zip.country_id and better_zip.country_id.code or False
                    if country_id_code:
                        if partner_vals["vat"] and not partner_vals["vat"].startswith(country_id_code):
                            partner_vals.update({
                                "vat": "%s%s" % (country_id_code, partner_vals["vat"])
                            })

            partner = res_partner_obj.search(domain, limit=1)
            if not partner:
                res_partner_obj.create(partner_vals)
            else:
                partner.write(partner_vals)

        return True

    def parse_sheet(self, sheet):
        res = []

        for row in sheet.rows:
            account_code = row[0].value
            if not account_code:
                continue
            try:
                int(account_code)
            except ValueError:
                continue

            street = row[3].value or ''
            if row[4].value:
                street += ' %s' % row[4].value

            res.append({
                "account_code": account_code,
                "name": u"%s" % row[1].value,
                "vat": row[2].value or False,
                "street": street.strip() or False,
                "zip": row[5].value or False,
                "city": row[6].value or False,
                "phone": row[7].value or False,
            })

        return res

    def get_excel_sheets(self, file_b64):
        """

        :param file_b64:
        :return:
        """
        excel_file_obj = TemporaryFile('wb+')
        excel_file_obj.write(file_b64)
        excel_file_obj.seek(0)

        workbook = openpyxl.load_workbook(excel_file_obj, data_only=True)
        return workbook.worksheets
