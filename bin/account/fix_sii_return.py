#!/usr/bin/env python
# -*- coding: utf-8 -*-

from tqdm import tqdm

from odooconnector import odooconnector

db = 'yourdb'
user = 'user'
pswd = 'yourpass'
url = 'http://localhost'
port = 8373

conn = odooconnector(url=url, db=db, user=user, pswd=pswd, port=port)

invoices_import = conn.search_read(
    "account.invoice.import", [("invoice_id", "!=", False), ("invoice_id.sii_return", "!=", False)], ["invoice_id"]
)

for invoice_import in tqdm(invoices_import):
    invoice = conn.read("account.invoice", invoice_import["invoice_id"][0], ["sii_return"])
    conn.write("account.invoice.import", invoice_import["id"], {
        "sii_return": invoice["sii_return"]
    })
