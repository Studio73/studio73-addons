# -*- coding: utf-8 -*-
# © 2017 Studio73 - Abraham Anes <abraham@studio73.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, exceptions, _


class AccountInvoiceMassMailing(models.TransientModel):
    _name = "account.invoice.mass_mailing"

    @api.model
    def _get_template_domain(self):
        id = self.env.ref('account.model_account_invoice').id
        return [('model_id', '=', id)]

    template_id = fields.Many2one(
        string="Plantilla",
        comodel_name='mail.template',
        domain=_get_template_domain,
        required=True
    )

    @api.multi
    def send_invoices(self):
        self.ensure_one()
        invoices = self.env['account.invoice'].browse(
            self._context['active_ids'])
        for i in invoices:
            ctx = i.action_invoice_sent()['context']
            w = self.env['mail.compose.message'].with_context(ctx).create({
                'model': 'account.invoice',
                'res_id': i.id,
                'template_id': self.template_id and self.template_id.id \
                               or False,
                'composition_mode': 'comment',
                'partner_ids': [(4, i.partner_id.id)],
            })
            oc_values = w.onchange_template_id(
                self.template_id.id,
                'comment',
                'account.invoice',
                i.id
            )
            w.write(oc_values['value'])
            w.send_mail_action()
        return True
