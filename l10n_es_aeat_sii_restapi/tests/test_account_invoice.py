# -*- coding: utf-8 -*-
# (c) 2017 Studio73 - Pablo Fuentes <pablo@studio73>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import json
import requests
from odoo.tests.common import HttpCase
from odoo.tools import mute_logger

USER = 'USER'
PSWD = 'PSWD'


class TestAccountInvoice(HttpCase):

    @mute_logger('requests.packages.urllib3.connectionpool')
    def setUp(self):
        super(TestAccountInvoice, self).setUp()

        self.url = "http://127.0.0.1:8080/api/account.invoice/"
        req = requests.post(
            'http://127.0.0.1:8080/web/session/authenticate',
            headers={
                'Content-type': 'application/json'
            },
            data=json.dumps({
                'params': {
                    'db': 'SII',
                    'login': USER,
                    'password': PSWD
                }
            })
        )
        self.cookies = {
            'session_id': json.loads(req.text)['result']['session_id']
        }
        self.invoice_ok = {
            'partner': {
                'vat': 'ESB98631534', 'name': 'Studio73', 'country_code': 'ES'
            },
            'type': 'out_invoice',
            'registration_key': '01',
            'lines': [1, 2, 3]
        }

    @mute_logger('requests.packages.urllib3.connectionpool')
    def get_post_request(self, invoice_data):
        req = requests.post(
            self.url,
            headers={
                'Content-type': 'application/json'
            },
            data=json.dumps({
                'params': invoice_data
            }),
            cookies=self.cookies
        )
        return req.json()['result']

    def test_00_partner(self):
        # 4100 - Partner is missing
        invoice = {
            'partner': {}
        }
        res = self.get_post_request(invoice)
        self.assertEqual(res['code'], 4100)
        # 4101 - Partner vat is missing
        invoice['partner'] = {
            'name': 'Studio73'
        }
        res = self.get_post_request(invoice)
        self.assertEqual(res['code'], 4101)
        # 4102 - Partner doesn't exists and name is missing
        invoice['partner'] = {
            'vat': 'ESB9863153'
        }
        res = self.get_post_request(invoice)
        self.assertEqual(res['code'], 4102)
        # 4103 - Partner doesn't exists and country code is missing
        invoice['partner'] = {
            'vat': 'ESB9863153',
            'name': 'Studio73'
        }
        res = self.get_post_request(invoice)
        self.assertEqual(res['code'], 4103)

    def test_01_invoice_type(self):
        invoice = {
            'partner': {
                'vat': 'ESB98631534',
                'name': 'Studio73',
                'country_code': 'ES'
            },
        }
        # 4200 - Invoice type is missing
        res = self.get_post_request(invoice)
        self.assertEqual(res['code'], 4200)
        # 4201 - Wrong invoice type
        invoice['type'] = 'asdf'
        res = self.get_post_request(invoice)
        self.assertEqual(res['code'], 4201)
        # 4202 - Supplier invoice number mandatory
        invoice['type'] = 'in_invoice'
        res = self.get_post_request(invoice)
        self.assertEqual(res['code'], 4202)

    def test_02_invoice_lines(self):
        invoice = self.invoice_ok.copy()
        invoice['lines'] = []
        # 4400 - Invoice with no lines
        res = self.get_post_request(invoice)
        self.assertEqual(res['code'], 4500)

    def test_03_invoice(self):
        invoice = self.invoice_ok.copy()
        invoice['registration_key'] = '25'
        # 4300 - Wrong registrarion key
        res = self.get_post_request(invoice)
        self.assertEqual(res['code'], 4300)
        # Invoice data OK
        res = self.get_post_request(self.invoice_ok)
        self.assertEqual(res['status'], 200)
