# -*- coding: utf-8 -*-
# (c) 2017 Studio73 - Pablo Fuentes <pablo@studio73>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from openerp import http, tools
from openerp.http import request
from openerp.addons.web.controllers.main import Session


class SessionCtrl(Session):

    @http.route('/api/authenticate', type='json', auth="none")
    def api_authenticate(self, login, password, db=False):
        if not db:
            db = request.httprequest.environ\
                        .get('HTTP_HOST', '').split(':')[0].replace('.', '-')
        if not db:
            return ''
        request.session.authenticate(db, login, password)
        return request.session_id

    @http.route('/api/logout', type='json', auth="user")
    def api_logout(self):
        request.session.logout()
