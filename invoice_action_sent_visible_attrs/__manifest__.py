# -*- coding: utf-8 -*-
{
    'name': 'Invoice action sent visible attrs',
    'version': '10.0.0.2.0',
    'sequence': 14,
    'category': 'Account',
    'author': 'Consultoría Informática Studio 73 S.L.',
    'summary': '',
    'website': 'http://www.studio73.es',
    'description': """
Mostrar el botón 'Enviar por correo electrónico' de las facturas en los estados 'draft', 'open' y 'paid'
""",
    'depends': [
        'account',
    ],
    'data': [
        'views/account_invoice_view.xml',
    ],
    'installable': True,
}
