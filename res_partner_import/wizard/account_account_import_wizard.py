# -*- coding: utf-8 -*-
# (c) 2017 Consultoría Informática Studio 73 S.L.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import openpyxl
from tempfile import TemporaryFile

from odoo import models, fields, api, _
from odoo.exceptions import Warning


class AccountAccountImportWizard(models.TransientModel):
    _name = 'account.account.import.wizard'

    file = fields.Binary(string="File to import")
    filename = fields.Char(string="Filename")

    @api.multi
    def import_xlsx(self):
        if not self.file:
            raise Warning(_(u"You must select the file with the accounting accounts to import"))

        sheets = self.get_excel_sheets(self.file.decode('base64'))
        accounts = self.parse_sheet(sheets[0])
        self.import_accounts(accounts)
        return True

    @api.multi
    def import_accounts(self, accounts):
        """

        :param data:
        :return:
        """
        account_account_obj = self.env["account.account"]

        user = self.env.user
        company_accounts_code_digits = user.company_id.accounts_code_digits

        for account_vals in accounts:
            code = str(account_vals["code"])
            account = account_account_obj.search([("code", "=", code)])

            if account:
                continue

            parent_code = code[:4].ljust(company_accounts_code_digits, '0')
            parent = account_account_obj.search([("code", "=", parent_code)], limit=1)
            if not parent:
                raise Warning(
                    _(u"The account with code '%s' needed to fill in the account '%s' "
                      u"data has not been found" % (parent_code, code))
                )

            account_vals.update({
                "user_type_id": parent.user_type_id.id,
                "tax_ids": [(6, 0, parent.tax_ids.ids)],
                "tag_ids": [(6, 0, parent.tag_ids.ids)],
                "reconcile": parent.reconcile,
                "deprecated": parent.deprecated,
                "centralized": parent.centralized,
            })
            account_account_obj.create(account_vals)

        return True

    def parse_sheet(self, sheet):
        res = []

        for row in sheet.rows:
            code = row[0].value
            if not code:
                continue
            try:
                int(code)
            except ValueError:
                continue

            res.append({
                "code": row[0].value,
                "name": row[1].value,
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
