# -*- coding: utf-8 -*-
{
    'name': 'Account Invoice Report',
    'version': '10.0.0.2.0',
    'sequence': 145,
    'category': 'Account',
    'author': 'Consultoría Informática Studio 73 S.L.',
    'summary': 'Custom account invoice report',
    'website': 'http://www.studio73.es',
    'description': """
Account invoice report
======================

Custom Qweb report, because Odoo's one is too ugly...

""",
    'depends': ['account', 'debrand_account_invoice_mail'],
    'data': [
        'views/res_company_view.xml',
        'views/report_invoice.xml'
    ],
    'installable': True,
}
