# -*- coding: utf-8 -*-
# (c) 2017 Studio73 - Pablo Fuentes <pablo@studio73>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from openerp.addons.web import http

old_serialize_exception = http.serialize_exception


def serialize_exception(e):
    response = old_serialize_exception(e)
    del response['debug']
    return response

http.serialize_exception = serialize_exception
