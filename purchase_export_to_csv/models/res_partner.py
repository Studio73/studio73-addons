# -*- coding: utf-8 -*-
# (c) 2017 Consultoría Informática Studio73 SL (contacto@studio73.es)
#          Ioan Galan <ioan@studio73.es>
#
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    shipping_code_hilding = fields.Integer(string="Dirección entrega Hilding")
