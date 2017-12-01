# -*- coding: utf-8 -*-
from openerp import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    display_qty_on_invoice = fields.Selection(
        string='Mostrar cantidades y precio unidad en facturas',
        selection=[
            ('always', 'Mostrar siempre'),
            ('higher', 'Mostrar solo si la cantidad es mayor que uno'),
            ('never', 'No mostrar nunca'),
        ],
        default='higher'
    )