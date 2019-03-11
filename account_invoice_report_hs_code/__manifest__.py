# -*- coding: utf-8 -*-
# Copyright 2019 Studio73 - Ioan Galan <ioan@studio73.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
{
    'name': 'Account Invoice Report HS Code',
    'version': '10.0.0.1.0',
    'sequence': 100,
    'category': 'Account',
    'license': 'AGPL-3',
    'author': 'Consultoría Informática Studio 73 S.L.',
    'summary': 'Show HS code in account invoice report',
    'website': 'http://www.studio73.es',
    'depends': [
        'account_invoice_report',
        'sale',
        'delivery'
    ],
    'data': [
        'views/report_invoice.xml'
    ],
    'installable': True,
}
