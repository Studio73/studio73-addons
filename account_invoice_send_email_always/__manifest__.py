# -*- coding: utf-8 -*-
# © 2017 Studio73 - Abraham Anes <abraham@studio73.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    'name': 'Account Invoice Send Email Always',
    'version': '10.0.1.0.0',
    'description': 'Allows send invoice by email in all states except cancel.',
    'license': 'AGPL-3',
    'author': "Consultoría Informática Studio 73 S.L., ",
    'category': 'account',
    'website': "https://www.studio73.es",
    'depends': ['account'],
    'data': [
        'views/account_invoice_view.xml',
    ],
    'installable': True,
}
