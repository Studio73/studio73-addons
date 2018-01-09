# -*- coding: utf-8 -*-
# © 2017 Studio73 - Abraham Anes <abraham@studio73.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    'name': 'Account invoice mass mailing',
    'version': '10.0.1.0.0',
    'category': 'Account',
    'sequence': 14,
    'description': """
    This module create a server action that launch a wizard where you can
     select the mail template for send all selected invoices.
    """,
    'author': 'Consultoría Informática Studio 73 S.L.',
    'website': 'http://www.studio73.es',
    'depends': [
        'account',
    ],
    'data': [
        'wizard/account_invoice_mass_mailing.xml',
    ],
    'demo': [],
    'test': [],
    'installable': True,
    'auto_install': False,
    'application': True,
}
