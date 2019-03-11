# -*- coding: utf-8 -*-
# Copyright 2019 Studio73 - Ioan Galan <ioan@studio73.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, models


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    @api.multi
    def show_hs_code_in_report(self):
        self.ensure_one()
        fp_intra = self.env.ref("l10n_es.1_fp_intra")
        fp_extra = self.env.ref("l10n_es.1_fp_extra")
        return self.fiscal_position_id.id in fp_intra.ids + fp_extra.ids
