# -*- coding: utf-8 -*-
# (c) 2017 Consultoría Informática Studio 73 S.L.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging
import json

from requests import Session

from openerp import _, api, exceptions, fields, models, SUPERUSER_ID
from openerp.modules.registry import RegistryManager
from openerp.exceptions import Warning

_logger = logging.getLogger(__name__)

try:
    from zeep import Client
    from zeep.transports import Transport
    from zeep.plugins import HistoryPlugin
except (ImportError, IOError) as err:
    _logger.debug(err)


try:
    from openerp.addons.connector.queue.job import job
    from openerp.addons.connector.session import ConnectorSession
except ImportError:
    _logger.debug('Can not `import connector`.')
    import functools

    def empty_decorator_factory(*argv, **kwargs):
        return functools.partial
    job = empty_decorator_factory

SII_STATES = [
    ('not_sent', 'Not sent'),
    ('sent', 'Sent'),
    ('sent_w_errors', 'Accepted with errors'),
    ('sent_modified', 'Registered in SII but last modifications not sent'),
    ('cancelled', 'Cancelled'),
    ('cancelled_modified', 'Cancelled in SII but last modifications not sent'),
]
SII_VERSION = '1.0'
SII_START_DATE = '2017-07-01'
SII_COUNTRY_CODE_MAPPING = {
    'RE': 'FR',
    'GP': 'FR',
    'MQ': 'FR',
    'GF': 'FR',
}


class AccountSpecificIntracommunityTransactions(models.Model):
    _name = 'account.specific.intracommunity.transactions'

    def _get_default_company(self):
        company_id = self.env["res.users"]._get_company()
        return company_id and self.env["res.company"].browse(company_id) or False

    @api.multi
    @api.depends('company_id', 'company_id.sii_enabled')
    def _compute_sii_enabled(self):
        for transaction in self:
            transaction.sii_enabled = transaction.company_id.sii_enabled

    fiscalyear_id = fields.Many2one(comodel_name='account.fiscalyear', string='Year', required=True)
    period_id = fields.Many2one("account.period", string="Period", required=True)

    name = fields.Char(string='Issuer name', required=True)
    issuer_identification_type = fields.Selection(
        string='Issuer identification type',
        selection=[('1', 'NIF'),
                   ('0', 'Other')],
        required=True,
        default='1'
    )
    issuer_vat = fields.Char(string='Issuer VAT')
    issuer_country_id = fields.Many2one(comodel_name='res.country', string='Issuer country')
    issuer_identifier = fields.Char(string='Issuer identifier')
    invoice_number = fields.Char(string='Supplier’s invoice number', required=True)
    invoice_date = fields.Date(string='Invoice date', required=True)
    counterparty_name = fields.Char(string='Counterparty name', required=True)
    counterparty_representative_vat = fields.Char(string='Representative counterparty VAT')
    counterparty_identification_type = fields.Selection(
        string='Counterparty identification type',
        selection=[('1', 'NIF'),
                   ('0', 'Other')],
        required=True,
        default='1'
    )
    counterparty_vat = fields.Char(string='Counterparty VAT')
    counterparty_country_id = fields.Many2one(comodel_name='res.country', string='Counterparty country')
    counterparty_identifier = fields.Char(string='Counterparty identifier')
    operation_type = fields.Selection(
        string='Operation type',
        selection=[('A', 'A - The transmission or receipt of goods to undertake partial reports or works stipulated in '
                         'Article 70, section one, Number 7 of the Tax Law (Law 37/1992).'),
                   ('B', 'B - Transfers of goods or intra-Community acquisitions of goods listed in Article 9.3 and Article'
                         ' 16.2 of the Tax Law (Law 37/1992).')],
        required=True
    )
    declared_key = fields.Selection(
        string='Declared key',
        selection=[('D', 'Filer'),
                   ('R', 'Sender')],
        required=True
    )
    country_id = fields.Many2one(
        comodel_name='res.country',
        string='Member state country',
        help='Code of the Member State of origin or transmission',
        required=True
    )
    operation_term = fields.Integer(string='Operation term')
    goods_description = fields.Char(string='Description of goods', required=True)
    operator_address = fields.Char(string='Operator address', required=True)
    other_inv_doc = fields.Char(
        string='Other invoices or documentation',
        help='Other invoices or documentation concerning the transactions in question'
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        required=True,
        default=_get_default_company
    )
    state = fields.Selection(
        string="State",
        selection=[("draft", "Draft"),
                   ("validated", "Validated"),
                   ("cancel", "Canceled")],
        default="draft"
    )

    sii_enabled = fields.Boolean(
        string='Enable SII', compute='_compute_sii_enabled',
    )
    sii_state = fields.Selection(
        selection=SII_STATES, string="SII send state", default='not_sent',
        readonly=True, copy=False,
        help="Indicates the state of this good in relation with the "
             "presentation at the SII",
    )
    sii_header_sent = fields.Text(
        string="SII last header sent", copy=False, readonly=True,
    )
    sii_content_sent = fields.Text(
        string="SII last content sent", copy=False, readonly=True,
    )
    sii_csv = fields.Char(string='SII CSV', copy=False, readonly=True)
    sii_return = fields.Text(string='SII Return', copy=False, readonly=True)
    sii_send_error = fields.Text(
        string='SII Send Error', readonly=True, copy=False,
    )
    sii_send_failed = fields.Boolean(
        string="SII send failed", copy=False,
        help="Indicates that the last attempt to communicate this good to "
             "the SII has failed. See SII return for details",
    )
    transaction_jobs_ids = fields.Many2many(
        comodel_name='queue.job', column1='transaction_id', column2='job_id',
        string="Connector Jobs", copy=False,
    )

    @api.multi
    def unlink(self):
        if not self._cancel_transaction_jobs():
            raise exceptions.Warning(_(
                'You can not delete this transaction because'
                ' there is a job running!'))
        elif self.sii_state and self.sii_state != 'not_sent':
            raise Warning(_("You cannot delete a transaction sent to SII."))
        return super(AccountSpecificIntracommunityTransactions, self).unlink()

    @api.multi
    def validate_transactions(self):
        for transaction in self.filtered('sii_enabled'):
            if transaction.sii_state == 'sent':
                transaction.sii_state = 'sent_modified'
            elif transaction.sii_state == 'cancelled':
                transaction.sii_state = 'cancelled_modified'
            company = transaction.company_id
            if company.sii_method != 'auto':
                continue
            transaction.state = 'validated'
            transaction._process_transaction_for_sii_send()

    @api.multi
    def cancel_transactions(self):
        if not self._cancel_transaction_jobs():
            raise exceptions.Warning(_(
                'You can not cancel this transaction because'
                ' there is a job running!'))
        if self.sii_state == 'sent':
            self.sii_state = 'sent_modified'
        elif self.sii_state == 'cancelled_modified':
            # Case when reopen a cancelled transaction, validate and cancel again
            # without any SII communication.
            self.sii_state = 'cancelled'
        self.state = 'cancel'
        transactions = self.filtered(
            lambda t: (t.sii_enabled and t.state in ['cancel'] and
                       t.sii_state in ['sent', 'sent_w_errors',
                                       'sent_modified'])
        )
        queue_obj = self.env['queue.job']
        for transaction in transactions:
            company = transaction.company_id
            if not company.use_connector:
                transaction._cancel_transaction_to_sii()
            else:
                eta = company._get_sii_eta()
                ctx = self.env.context.copy()
                ctx.update(company_id=company.id)
                session = ConnectorSession(
                    self.env.cr, SUPERUSER_ID, context=ctx,
                )
                new_delay = cancel_one_transaction.delay(
                    session, 'account.specific.intracommunity.transactions', transaction.id, eta=eta)
                queue_ids = queue_obj.search([
                    ('uuid', '=', new_delay)
                ], limit=1)
                transaction.sudo().transaction_jobs_ids |= queue_ids

    @api.multi
    def to_draft_transactions(self):
        if not self._cancel_transaction_jobs():
            raise exceptions.Warning(_(
                'You can not set to draft this transaction because'
                ' there is a job running!'))
        self.state = 'draft'

    @api.multi
    def _cancel_transaction_jobs(self):
        for queue in self.mapped('transaction_jobs_ids'):
            if queue.state == 'started':
                return False
            elif queue.state in ('pending', 'enqueued', 'failed'):
                queue.sudo().unlink()
        return True

    @api.multi
    def _connect_sii(self, wsdl):
        today = fields.Date.today()
        sii_config = self.env['l10n.es.aeat.sii'].search([
            ('company_id', '=', self.company_id.id),
            ('public_key', '!=', False),
            ('private_key', '!=', False),
            '|',
            ('date_start', '=', False),
            ('date_start', '<=', today),
            '|',
            ('date_end', '=', False),
            ('date_end', '>=', today),
            ('state', '=', 'active'),
        ], limit=1)
        if sii_config:
            public_crt = sii_config.public_key
            private_key = sii_config.private_key
        else:
            public_crt = self.env['ir.config_parameter'].get_param(
                'l10n_es_aeat_sii.publicCrt', False)
            private_key = self.env['ir.config_parameter'].get_param(
                'l10n_es_aeat_sii.privateKey', False)
        session = Session()
        session.cert = (public_crt, private_key)
        transport = Transport(session=session)
        history = HistoryPlugin()
        client = Client(wsdl=wsdl, transport=transport, plugins=[history])
        return client

    @api.multi
    def _change_date_format(self, date):
        datetimeobject = fields.Date.from_string(date)
        new_date = datetimeobject.strftime('%d-%m-%Y')
        return new_date

    @api.multi
    def _get_sii_issuer_country_code(self):
        self.ensure_one()
        country_code = (self.issuer_country_id.code or (self.issuer_vat or '')[:2]).upper()
        return SII_COUNTRY_CODE_MAPPING.get(country_code, country_code)

    @api.multi
    def _get_sii_counterparty_country_code(self):
        self.ensure_one()
        country_code = (self.counterparty_country_id.code or (self.counterparty_vat or '')[:2]).upper()
        return SII_COUNTRY_CODE_MAPPING.get(country_code, country_code)

    @api.multi
    def _sii_check_exceptions(self):
        """Inheritable method for exceptions control when sending SII.
        """
        self.ensure_one()
        if not self.company_id.sii_enabled:
            raise exceptions.Warning(
                _("This company doesn't have SII enabled.")
            )

    @api.multi
    def _get_sii_transaction_dict(self, cancel=False):
        self.ensure_one()
        self._sii_check_exceptions()

        """Build dict with data to send to AEAT WS for transaction

                :param cancel: It indicates if the dictionary is for sending a
                  cancellation of the transaction.
                :return: transactions (dict) : Dict XML with data for this transaction.
                """
        self.ensure_one()
        invoice_date = self._change_date_format(self.invoice_date)
        ejercicio = fields.Date.from_string(
            self.fiscalyear_id.date_start).year
        periodo = '%02d' % fields.Date.from_string(
            self.period_id.date_start).month
        transaction_dict = {
            "IDFactura": {
                "IDEmisorFactura": {
                    "NombreRazon": self.name,
                },
                "NumSerieFacturaEmisor": (self.invoice_number or '')[0:60],
                "FechaExpedicionFacturaEmisor": invoice_date,
            },
            "PeriodoImpositivo": {
                "Ejercicio": ejercicio,
                "Periodo": periodo,
            },
        }

        if self.issuer_identification_type == '1':
            transaction_dict["IDFactura"]["IDEmisorFactura"].update({'NIF': self.issuer_vat[2:]})
        elif self.issuer_identification_type == '0':
            transaction_dict["IDFactura"]["IDEmisorFactura"].update({
                "IDOtro": {
                    "CodigoPais": self._get_sii_issuer_country_code(),
                    "IDType": '02',
                    "ID": self.issuer_identifier,
                }
            })

        if not cancel:
            transaction_dict["Contraparte"] = {"NombreRazon": self.counterparty_name}
            if self.counterparty_identification_type == '1':
                transaction_dict["Contraparte"].update({'NIF': self.counterparty_vat[2:]})
            elif self.counterparty_identification_type == '0':
                transaction_dict["Contraparte"].update({
                    "IDOtro": {
                        "CodigoPais": self._get_sii_counterparty_country_code(),
                        "IDType": '02',
                        "ID": self.counterparty_identifier,
                    }
                })
            transaction_dict["OperacionIntracomunitaria"] = {
                "TipoOperacion": self.operation_type,
                "ClaveDeclarado": self.declared_key,
                "EstadoMiembro": (self.country_id.code).upper(),
                "DescripcionBienes": self.goods_description,
                "DireccionOperador": self.operator_address,
            }
            if self.counterparty_representative_vat:
                transaction_dict["Contraparte"].update({'NIFRepresentante': self.counterparty_representative_vat[2:]})
            if self.operation_term:
                transaction_dict["OperacionIntracomunitaria"].update({'PlazoOperacion': self.operation_term})
            if self.other_inv_doc:
                transaction_dict["OperacionIntracomunitaria"].update({'FacturasODocumentacion': self.other_inv_doc})
        return transaction_dict

    @api.multi
    def _get_sii_header(self, tipo_comunicacion=False, cancellation=False):
        """Builds SII send header

        :param tipo_comunicacion String 'A0': new reg, 'A1': modification
        :param cancellation Bool True when the communitacion es for transaction
            cancellation
        :return Dict with header data depending on cancellation
        """
        self.ensure_one()
        company = self.company_id
        if not company.vat:
            raise exceptions.Warning(_(
                "No VAT configured for the company '{}'").format(company.name))
        header = {
            "IDVersionSii": SII_VERSION,
            "Titular": {
                "NombreRazon": self.company_id.name[0:120],
                "NIF": self.company_id.vat[2:]}
        }
        if not cancellation:
            header.update({"TipoComunicacion": tipo_comunicacion})
        return header

    @api.multi
    def _send_transaction_to_sii(self):
        for transaction in self.filtered(lambda a: a.state in ['validated']):
            company = transaction.company_id
            wsdl = self.env['ir.config_parameter'].get_param(
                'l10n_es_aeat_sii.wsdl_ic', False)
            port_name = 'SuministroOpIntracomunitarias'
            if company.sii_test:
                port_name += 'Pruebas'
            client = self._connect_sii(wsdl)
            serv = client.bind('siiService', port_name)
            if transaction.sii_state == 'not_sent':
                tipo_comunicacion = 'A0'
            else:
                tipo_comunicacion = 'A1'
            header = transaction._get_sii_header(tipo_comunicacion)
            transaction_vals = {
                'sii_header_sent': json.dumps(header, indent=4),
            }
            try:
                transaction_dict = transaction._get_sii_transaction_dict()
                transaction_vals['sii_content_sent'] = json.dumps(transaction_dict, indent=4)
                res = serv.SuministroLRDetOperacionIntracomunitaria(header, transaction_dict)
                res_line = res['RespuestaLinea'][0]
                if res['EstadoEnvio'] == 'Correcto':
                    transaction_vals.update({
                        'sii_state': 'sent',
                        'sii_csv': res['CSV'],
                        'sii_send_failed': False,
                    })
                elif res['EstadoEnvio'] == 'ParcialmenteCorrecto' and \
                                res_line['EstadoRegistro'] == 'AceptadoConErrores':
                    transaction_vals.update({
                        'sii_state': 'sent_w_errors',
                        'sii_csv': res['CSV'],
                        'sii_send_failed': True,
                    })
                else:
                    transaction_vals['sii_send_failed'] = True
                    transaction_vals['sii_return'] = res
                send_error = False
                if res_line['CodigoErrorRegistro']:
                    send_error = u"{} | {}".format(
                        unicode(res_line['CodigoErrorRegistro']),
                        unicode(res_line['DescripcionErrorRegistro'])[:60])
                transaction_vals['sii_send_error'] = send_error
                transaction.write(transaction_vals)
            except Exception as fault:
                new_cr = RegistryManager.get(self.env.cr.dbname).cursor()
                env = api.Environment(new_cr, self.env.uid, self.env.context)
                transaction = env['account.specific.intracommunity.transactions'].browse(self.id)
                transaction_vals.update({
                    'sii_send_failed': True,
                    'sii_send_error': fault,
                    'sii_return': fault,
                })
                transaction.write(transaction_vals)
                new_cr.commit()
                new_cr.close()
                raise

    @api.multi
    def _cancel_transaction_to_sii(self):
        for transaction in self.filtered(lambda t: t.state in ['cancel']):
            company = transaction.company_id
            wsdl = self.env['ir.config_parameter'].get_param(
                'l10n_es_aeat_sii.wsdl_ic', False)
            port_name = 'SuministroOpIntracomunitarias'
            if company.sii_test:
                port_name += 'Pruebas'
            client = self._connect_sii(wsdl)
            serv = client.bind('siiService', port_name)

            header = transaction._get_sii_header(cancellation=True)
            try:
                transaction_dict = transaction._get_sii_transaction_dict(cancel=True)
                res = serv.AnulacionLRDetOperacionIntracomunitaria(header, transaction_dict)
                if res['EstadoEnvio'] == 'Correcto':
                    transaction.sii_state = 'cancelled'
                    transaction.sii_csv = res['CSV']
                    transaction.sii_send_failed = False
                else:
                    transaction.sii_send_failed = True
                transaction.sii_return = res
                send_error = False
                res_line = res['RespuestaLinea'][0]
                if res_line['CodigoErrorRegistro']:
                    send_error = u"{} | {}".format(
                        unicode(res_line['CodigoErrorRegistro']),
                        unicode(res_line['DescripcionErrorRegistro'])[:60])
                transaction.sii_send_error = send_error
            except Exception as fault:
                new_cr = RegistryManager.get(self.env.cr.dbname).cursor()
                env = api.Environment(new_cr, self.env.uid, self.env.context)
                transaction = env['account.specific.intracommunity.transactions'].browse(self.id)
                transaction.sii_send_error = fault
                transaction.sii_send_failed = True
                transaction.sii_return = fault
                new_cr.commit()
                new_cr.close()
                raise

    @api.multi
    def _process_transaction_for_sii_send(self):
        """Process transactions for sending to the SII. Adds general checks from
        configuration parameters and transaction availability for SII. If the
        transaction is to be sent the decides the send method: direct send or
        via connector depending on 'Use connector' configuration"""
        queue_obj = self.env['queue.job'].sudo()
        for transaction in self:
            company = transaction.company_id
            if not company.use_connector:
                transaction._send_transactionto_sii()
            else:
                eta = company._get_sii_eta()
                ctx = self.env.context.copy()
                ctx.update(company_id=company.id)
                session = ConnectorSession(
                    self.env.cr, SUPERUSER_ID, context=ctx,
                )
                new_delay = confirm_one_transaction.delay(
                    session, 'account.specific.intracommunity.transactions', transaction.id,
                    eta=eta if not transaction.sii_send_failed else False,
                )
                transaction.sudo().transaction_jobs_ids |= queue_obj.search(
                    [('uuid', '=', new_delay)], limit=1,
                )

@job(default_channel='root.transaction_validate_sii')
def confirm_one_transaction(session, model_name, transaction_id):
    model = session.env[model_name]
    transaction = model.browse(transaction_id)
    if transaction.exists():
        transaction._send_transaction_to_sii()

@job(default_channel='root.transaction_validate_sii')
def cancel_one_transaction(session, model_name, transaction_id):
    model = session.env[model_name]
    transaction = model.browse(transaction_id)
    if transaction.exists():
        transaction._cancel_transaction_to_sii()