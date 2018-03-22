# -*- coding: utf-8 -*-
# Copyright 2018 Studio73 - Ioan Galan <abraham@studio73.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    'name': 'Account Invoice Report Stock Picking',
    'version': '10.0.0.1.0',
    'sequence': 173,
    'category': 'Account',
    'author': 'Consultoría Informática Studio 73 S.L.',
    'summary': 'Custom account invoice report',
    'website': 'http://www.studio73.es',
    'description': """
Account invoice report stock picking
=======================================
Add stock picking references to our custom invoice report.
""",
    'depends': [
        'account_invoice_report',
        'stock_picking_invoice_link',
    ],
    'data': [
        'views/report_invoice.xml'
    ],
    'installable': True,
}
