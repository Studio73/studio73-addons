# -*- coding: utf-8 -*-
# (c) 2017 Consultoría Informática Studio 73 S.L.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models, fields, api


class AccountAccount(models.Model):
    _inherit = 'account.account'

    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):
        """Improves the search of accounts using a dot to fill the zeroes
            (like 43.27 to search account 43000027)"""
        args = args[:]
        pos = 0
        while pos < len(args):
            if args[pos][0] == 'code' and args[pos][1] in (
            'like', 'ilike', '=ilike', '=like') and args[pos][2]:
                query = args[pos][2].replace('%', '')
                if '.' in query:
                    query = query.partition('.')
                    self.env.cr.execute("""
                    SELECT id
                    FROM account_account
                    WHERE code ~ ('^' || %s || '0+' || %s || '$')""",
                                        (query[0], query[2]))
                    ids = [x[0] for x in self.env.cr.fetchall()]
                    if ids:
                        args[pos] = ('id', 'in', ids)
                elif ',' in query:
                    query = query.partition(',')
                    self.env.cr.execute("""
                    SELECT id
                    FROM account_account
                    WHERE code ~ ('^' || %s || '0+' || %s || '$')""",
                                        (query[0], query[2]))
                    ids = [x[0] for x in self.env.cr.fetchall()]
                    if ids:
                        args[pos] = ('id', 'in', ids)
            pos += 1
        return super(AccountAccount, self).search(
            args, offset, limit, order, count)
