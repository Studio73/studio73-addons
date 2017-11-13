# -*- coding: utf-8 -*-
# (c) 2017 Consultoría Informática Studio73 SL (contacto@studio73.es)
#          Pablo Fuentes <pablo@studio73.es>
#
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models, api


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.multi
    def action_quotation_send(self):
        res = super(SaleOrder, self).action_quotation_send()
        res['context']['custom_layout'] = \
            'debrand_mail_layout.mail_template_debranded'
        return res
