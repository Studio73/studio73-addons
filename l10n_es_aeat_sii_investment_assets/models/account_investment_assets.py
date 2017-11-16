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


class AccountInvestmentAssets(models.Model):
    _name = 'account.investment.assets'

    def _get_default_company(self):
        company_id = self.env["res.users"]._get_company()
        return company_id and self.env["res.company"].browse(company_id) or False

    @api.multi
    @api.depends('company_id', 'company_id.sii_enabled')
    def _compute_sii_enabled(self):
        for asset in self:
            asset.sii_enabled = asset.company_id.sii_enabled

    fiscalyear_id = fields.Many2one(comodel_name='account.fiscalyear', string='Year', required=True)
    period = fields.Selection(
        string='Period',
        selection=[('0A', '0A')],
        required=True,
        default='0A'
    )
    name = fields.Char(string='Issuer name', required=True)
    identification_type = fields.Selection(
        string='Identification type',
        selection=[('1', 'NIF'),
                   ('0', 'Other')],
        required=True,
        default='1'
    )
    vat = fields.Char(string='Issuer VAT')
    country_id = fields.Many2one(comodel_name='res.country', string='Country')
    vat_type = fields.Selection(
        string="Recipient’s VAT-Id Type",
        selection=[('02', u'02 - NIF-VAT'),
                   ('03', u'03 - Passport'),
                   ('04', u'04 - Official id document issued by the country or territory of residence'),
                   ('05', u'05 - Certificate of residence'),
                   ('06', u'06 - Other documents'),
                   ('07', u'07 - NO CENSUS')
                   ]
    )
    identifier = fields.Char(string='Identifier')
    invoice_number = fields.Char(string='Supplier’s invoice number', required=True)
    invoice_date = fields.Date(string='Invoice date', required=True)
    asset_identifier = fields.Char(string='Asset identifier', required=True)
    utilization_start_date = fields.Date(string='Utilization start date', required=True)
    definitive_annual_proportion = fields.Float(string='Definitive annual proportion', required=True)
    definitive_annual_regularization = fields.Float(string='Definitive annual regularization')
    delivery_identification = fields.Char(string='Delivery identification')
    regularization_deduction_done = fields.Float(string='Regularitzation deduction done')  # Esto ta mal segur

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
        help="Indicates the state of this asset in relation with the "
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
        help="Indicates that the last attempt to communicate this asset to "
             "the SII has failed. See SII return for details",
    )
    asset_jobs_ids = fields.Many2many(
        comodel_name='queue.job', column1='asset_id', column2='job_id',
        string="Connector Jobs", copy=False,
    )

    @api.multi
    def unlink(self):
        if not self._cancel_asset_jobs():
            raise exceptions.Warning(_(
                'You can not delete this asset because'
                ' there is a job running!'))
        elif self.sii_state and self.sii_state != 'not_sent':
            raise Warning(_("You cannot delete a asset sent to SII."))
        return super(AccountInvestmentAssets, self).unlink()

    @api.multi
    def validate_assets(self):
        for asset in self.filtered('sii_enabled'):
            if asset.sii_state == 'sent':
                asset.sii_state = 'sent_modified'
            elif asset.sii_state == 'cancelled':
                asset.sii_state = 'cancelled_modified'
            company = asset.company_id
            if company.sii_method != 'auto':
                continue
            asset.state = 'validated'
            asset._process_asset_for_sii_send()

    @api.multi
    def cancel_assets(self):
        if not self._cancel_asset_jobs():
            raise exceptions.Warning(_(
                'You can not cancel this asset because'
                ' there is a job running!'))
        if self.sii_state == 'sent':
            self.sii_state = 'sent_modified'
        elif self.sii_state == 'cancelled_modified':
            # Case when reopen a cancelled asset, validate and cancel again
            # without any SII communication.
            self.sii_state = 'cancelled'
        self.state = 'cancel'
        assets = self.filtered(
            lambda a: (a.sii_enabled and a.state in ['cancel'] and
                       a.sii_state in ['sent', 'sent_w_errors',
                                       'sent_modified'])
        )
        queue_obj = self.env['queue.job']
        for asset in assets:
            company = asset.company_id
            if not company.use_connector:
                asset._cancel_asset_to_sii()
            else:
                eta = company._get_sii_eta()
                ctx = self.env.context.copy()
                ctx.update(company_id=company.id)
                session = ConnectorSession(
                    self.env.cr, SUPERUSER_ID, context=ctx,
                )
                new_delay = cancel_one_asset.delay(
                    session, 'account.investment.assets', asset.id, eta=eta)
                queue_ids = queue_obj.search([
                    ('uuid', '=', new_delay)
                ], limit=1)
                asset.sudo().asset_jobs_ids |= queue_ids

    @api.multi
    def to_draft_assets(self):
        if not self._cancel_asset_jobs():
            raise exceptions.Warning(_(
                'You can not set to draft this asset because'
                ' there is a job running!'))
        self.state = 'draft'

    @api.multi
    def _cancel_asset_jobs(self):
        for queue in self.mapped('asset_jobs_ids'):
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
    def _get_sii_country_code(self):
        self.ensure_one()
        country_code = (self.country_id.code or (self.vat or '')[:2]).upper()
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
    def _get_sii_asset_dict(self, cancel=False):
        self.ensure_one()
        self._sii_check_exceptions()

        """Build dict with data to send to AEAT WS for asset

                :param cancel: It indicates if the dictionary is for sending a
                  cancellation of the asset.
                :return: assets (dict) : Dict XML with data for this asset.
                """
        self.ensure_one()
        invoice_date = self._change_date_format(self.invoice_date)
        utilization_date = self._change_date_format(self.utilization_start_date)
        ejercicio = fields.Date.from_string(
            self.fiscalyear_id.date_start).year
        asset_dict = {
            "IDFactura": {
                "IDEmisorFactura": {
                    "NombreRazon": self.name,
                },
                "NumSerieFacturaEmisor": (self.invoice_number or '')[0:60],
                "FechaExpedicionFacturaEmisor": invoice_date,
            },
            "PeriodoImpositivo": {
                "Ejercicio": ejercicio,
                "Periodo": self.period,
            },
        }

        if self.identification_type == '1':
            asset_dict["IDFactura"]["IDEmisorFactura"].update({'NIF': self.vat[2:]})
        elif self.identification_type == '0':
            asset_dict["IDFactura"]["IDEmisorFactura"].update({
                "IDOtro": {
                    "CodigoPais": self._get_sii_country_code(),
                    "IDType": self.vat_type,
                    "ID": self.identifier,
                }
            })

        if not cancel:
            asset_dict["BienesInversion"] = {
                "IdentificacionBien": self.asset_identifier,
                "FechaInicioUtilizacion": utilization_date,
                "ProrrataAnualDefinitiva": self.definitive_annual_proportion,
            }
            if self.definitive_annual_regularization:
                asset_dict["BienesInversion"].update(
                    {'RegularizacionAnualDeduccion': (self.definitive_annual_regularization)}
                )
            if self.delivery_identification:
                asset_dict["BienesInversion"].update(
                    {'IdentificacionEntrega': (self.delivery_identification)}
                )
            if self.regularization_deduction_done:
                asset_dict["BienesInversion"].update(
                    {'RegularizacionDeduccionEfectuada': (self.regularization_deduction_done)}
                )
        else:
            asset_dict["IdentificacionBien"] = self.asset_identifier
        return asset_dict

    @api.multi
    def _get_sii_header(self, tipo_comunicacion=False, cancellation=False):
        """Builds SII send header

        :param tipo_comunicacion String 'A0': new reg, 'A1': modification
        :param cancellation Bool True when the communitacion es for asset
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
    def _send_asset_to_sii(self):
        for asset in self.filtered(lambda a: a.state in ['validated']):
            company = asset.company_id
            wsdl = self.env['ir.config_parameter'].get_param(
                'l10n_es_aeat_sii.wsdl_pi', False)
            port_name = 'SuministroBienesInversion'
            if company.sii_test:
                port_name += 'Pruebas'
            client = self._connect_sii(wsdl)
            serv = client.bind('siiService', port_name)
            if asset.sii_state == 'not_sent':
                tipo_comunicacion = 'A0'
            else:
                tipo_comunicacion = 'A1'
            header = asset._get_sii_header(tipo_comunicacion)
            asset_vals = {
                'sii_header_sent': json.dumps(header, indent=4),
            }
            try:
                asset_dict = asset._get_sii_asset_dict()
                asset_vals['sii_content_sent'] = json.dumps(asset_dict, indent=4)
                res = serv.SuministroLRBienesInversion(header, asset_dict)
                res_line = res['RespuestaLinea'][0]
                if res['EstadoEnvio'] == 'Correcto':
                    asset_vals.update({
                        'sii_state': 'sent',
                        'sii_csv': res['CSV'],
                        'sii_send_failed': False,
                    })
                elif res['EstadoEnvio'] == 'ParcialmenteCorrecto' and \
                                res_line['EstadoRegistro'] == 'AceptadoConErrores':
                    asset_vals.update({
                        'sii_state': 'sent_w_errors',
                        'sii_csv': res['CSV'],
                        'sii_send_failed': True,
                    })
                else:
                    asset_vals['sii_send_failed'] = True
                asset_vals['sii_return'] = res
                send_error = False
                if res_line['CodigoErrorRegistro']:
                    send_error = u"{} | {}".format(
                        unicode(res_line['CodigoErrorRegistro']),
                        unicode(res_line['DescripcionErrorRegistro'])[:60])
                asset_vals['sii_send_error'] = send_error
                asset.write(asset_vals)
            except Exception as fault:
                new_cr = RegistryManager.get(self.env.cr.dbname).cursor()
                env = api.Environment(new_cr, self.env.uid, self.env.context)
                asset = env['account.investment.assets'].browse(self.id)
                asset_vals.update({
                    'sii_send_failed': True,
                    'sii_send_error': fault,
                    'sii_return': fault,
                })
                asset.write(asset_vals)
                new_cr.commit()
                new_cr.close()
                raise

    @api.multi
    def _cancel_asset_to_sii(self):
        for asset in self.filtered(lambda a: a.state in ['cancel']):
            company = asset.company_id
            wsdl = self.env['ir.config_parameter'].get_param(
                'l10n_es_aeat_sii.wsdl_pi', False)
            port_name = 'SuministroBienesInversion'
            if company.sii_test:
                port_name += 'Pruebas'
            client = self._connect_sii(wsdl)
            serv = client.bind('siiService', port_name)

            header = asset._get_sii_header(cancellation=True)
            try:
                asset_dict = asset._get_sii_asset_dict(cancel=True)
                res = serv.AnulacionLRBienesInversion(header, asset_dict)
                if res['EstadoEnvio'] == 'Correcto':
                    asset.sii_state = 'cancelled'
                    asset.sii_csv = res['CSV']
                    asset.sii_send_failed = False
                else:
                    asset.sii_send_failed = True
                asset.sii_return = res
                send_error = False
                res_line = res['RespuestaLinea'][0]
                if res_line['CodigoErrorRegistro']:
                    send_error = u"{} | {}".format(
                        unicode(res_line['CodigoErrorRegistro']),
                        unicode(res_line['DescripcionErrorRegistro'])[:60])
                asset.sii_send_error = send_error
            except Exception as fault:
                new_cr = RegistryManager.get(self.env.cr.dbname).cursor()
                env = api.Environment(new_cr, self.env.uid, self.env.context)
                asset = env['account.investment.assets'].browse(self.id)
                asset.sii_send_error = fault
                asset.sii_send_failed = True
                asset.sii_return = fault
                new_cr.commit()
                new_cr.close()
                raise

    @api.multi
    def _process_asset_for_sii_send(self):
        """Process assets for sending to the SII. Adds general checks from
        configuration parameters and asset availability for SII. If the
        asset is to be sent the decides the send method: direct send or
        via connector depending on 'Use connector' configuration"""
        queue_obj = self.env['queue.job'].sudo()
        for asset in self:
            company = asset.company_id
            if not company.use_connector:
                asset._send_asset_to_sii()
            else:
                eta = company._get_sii_eta()
                ctx = self.env.context.copy()
                ctx.update(company_id=company.id)
                session = ConnectorSession(
                    self.env.cr, SUPERUSER_ID, context=ctx,
                )
                new_delay = confirm_one_asset.delay(
                    session, 'account.investment.assets', asset.id,
                    eta=eta if not asset.sii_send_failed else False,
                )
                asset.sudo().asset_jobs_ids |= queue_obj.search(
                    [('uuid', '=', new_delay)], limit=1,
                )

@job(default_channel='root.asset_validate_sii')
def confirm_one_asset(session, model_name, asset_id):
    model = session.env[model_name]
    asset = model.browse(asset_id)
    if asset.exists():
        asset._send_asset_to_sii()

@job(default_channel='root.asset_validate_sii')
def cancel_one_asset(session, model_name, asset_id):
    model = session.env[model_name]
    asset = model.browse(asset_id)
    if asset.exists():
        asset._cancel_asset_to_sii()