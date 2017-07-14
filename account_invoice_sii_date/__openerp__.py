# -*- coding: utf-8 -*-
# (c) 2017 Studio73 - Jordi Tolsa <jordi@studio73>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Fecha de envío al SII",
    'version': '1.0',
    'category': 'accounting',
    'sequence': 14,
    'description': """
    """,
    'author': 'Consultoría Informática Studio 73 S.L.',
    'website': 'http://www.studio73.es',
    'depends': [
        'account_invoice_entry_date'
    ],
    'data': [
        'views/account_view.xml'
    ],
    'demo': [],
    'test': [],
    'installable': True,
}
