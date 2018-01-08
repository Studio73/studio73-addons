# -*- coding: utf-8 -*-
{
    'name': 'Account Invoice Supplier OrderBy',
    'version': '10.0.0.1.0',
    'sequence': 145,
    'category': 'Account',
    'author': 'Consultoría Informática Studio 73 S.L.',
    'summary': 'Custom account invoice report',
    'website': 'http://www.studio73.es',
    'description': """
Account invoice
===============

Add a order in the tree view of the account invoice of supplier to order by 
the odoo invoice number.

""",
    'depends': [
        'account'
    ],
    'data': [
        'views/account_invoice.xml'
    ],
    'installable': True,
}
