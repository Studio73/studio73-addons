# -*- coding: utf-8 -*-
# (c) 2017 Consultoría Informática Studio 73 S.L.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models, fields, api, _


class AeatSiiMappingRegistrationKeys(models.Model):
    _inherit = 'aeat.sii.mapping.registration.keys'

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        recs = self.browse()
        if name:
            recs = self.search([('code', operator, name)] + args, limit=limit)
        if not recs:
            recs = super(AeatSiiMappingRegistrationKeys, self).name_search(name, args, operator, limit)
            return recs
        return recs.name_get()
