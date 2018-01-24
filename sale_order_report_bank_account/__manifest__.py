# -*- coding: utf-8 -*-
{
    'name': 'Sale Order Report Payment Mode',
    'version': '10.0.1.0.0',
    'category': 'Account',
    'author': 'Consultoría Informática Studio 73 S.L.',
    'summary': 'Sale Order Report Payment Mode',
    'website': 'http://www.studio73.es',
    'description': """
Sale order report payment mode
==============================

This modulo override the payment mode of the sale order report, adding the accounts if has.

""",
    'depends': [
        'account_payment_sale',
    ],
    'data': [
        'views/report_saleorder.xml'
    ],
    'installable': True,
}
