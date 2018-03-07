# -*- coding: utf-8 -*-
# Copyright 2018 Studio73 - Abraham Anes <abraham@studio73.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    'name': 'Account Invoice Report Shipping Address',
    'version': '10.0.0.1.0',
    'sequence': 173,
    'category': 'Account',
    'author': 'Consultoría Informática Studio 73 S.L.',
    'summary': 'Custom account invoice report',
    'website': 'http://www.studio73.es',
    'description': """
Account invoice report shipping address
=======================================

Add shipping addres to our custom invoice report.

""",
    'depends': [
        'sale',
        'account_invoice_report'
    ],
    'data': [
        'views/report_invoice.xml'
    ],
    'installable': True,
    'auto_install': True,
}
