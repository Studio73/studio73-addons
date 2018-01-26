# -*- coding: utf-8 -*-
# (c) 2017 Studio73 - Abraham Anes <abraham@studio73>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
{
    "name": "Suministro Inmediato de Información - Bienes de Inversión",
    "version": "10.0.1.0.0",
    "category": "Accounting & Finance",
    "website": "https://odoo-community.org/",
    "author": "Consultoría Informática Studio 73 S.L., ",
    "license": "AGPL-3",
    "depends": [
        "l10n_es_aeat_sii",
    ],
    "data": [
        'views/account_investment_assets_view.xml',
        'security/ir.model.access.csv'
    ],
    "installable": True,
}