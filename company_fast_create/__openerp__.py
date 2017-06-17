# -*- coding: utf-8 -*-
# (c) 2017 Studio73 - Pablo Fuentes <pablo@studio73>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    'name': 'Configurar compañías rapidamente con un único botón',
    'version': '1.0',
    'category': 'Account',
    'sequence': 14,
    'description': """
    Permite crear todos los datos necesarios de una compañía pulsando un solo botón:
        - Creación de diarios contables: Ventas, Compras, Abonos ventas y Abonos compras
        - Creación del año fiscal actual y los periodos mensuales
        - Creación mediante account_chart_update de todo el plan de cuentas e impuestos
    """,
    'author': 'Consultoría Informática Studio 73 S.L.',
    'website': 'http://www.studio73.es',
    'depends': ['base', 'account_chart_update'],
    'data': [
        "views/res_company_view.xml",
    ],
    'demo': [],
    'test': [],
    'installable': True,
    'auto_install': False,
    'application': True,
}

