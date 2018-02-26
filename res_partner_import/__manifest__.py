# -*- coding: utf-8 -*-
# (c) 2017 Studio73 - Pablo Fuentes <pablo@studio73>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Import partners and accounts",
    "version": "10.0.1.0.0",
    "category": "Accounting & Finance",
    "website": "http://www.studio73.es",
    "author": "Consultoría Informática Studio 73 S.L., ",
    "license": "AGPL-3",
    "depends": [
        "cis_partner_sequence",
    ],
    "data": [
        "wizard/account_account_import_wizard_view.xml",
        "wizard/res_partner_import_wizard_view.xml",
        "security/ir.model.access.csv",
    ],
    "installable": True,
    'external_dependencies': {
        'python': ['openpyxl']
    },
}
