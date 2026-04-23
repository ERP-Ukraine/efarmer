import json
import logging
from datetime import datetime, timedelta

import psycopg2
from cryptography.fernet import Fernet
from odoo.exceptions import UserError
from odoo.modules.registry import Registry

from odoo import _, api, fields, models

from .ksef_client import KsefAuthenticationStatusError, KsefClient, KsefClientError

_logger = logging.getLogger(__name__)

ENC_KEY = 'trilab_ksef.enc_key'


class ResCompany(models.Model):
    _inherit = 'res.company'

    x_ksef_settings_id = fields.Many2one(comodel_name='ksef.settings', string='KSeF Settings')
    x_ksef_enable_barcodes = fields.Boolean('KSeF Enable Barcodes', help='Show Barcodes on Invoice Lines')
    x_ksef_enable_seller_contact_info = fields.Boolean(
        'KSeF Enable Seller Contact Info', help='Show Seller email and phone on Sale Invoice'
    )
    x_ksef_enable_buyer_contact_info = fields.Boolean(
        'KSeF Enable Buyer Contact Info', help='Show Buyer email and phone on Sale Invoice'
    )
    x_ksef_enable_ignore_zero_amount_lines = fields.Boolean(
        'KSeF Ignore Zero Amount Lines', help="Don't send Invoice's Zero Amount Lines"
    )
    x_ksef_enable_outgoing_stock_pickings = fields.Boolean(
        'KSeF Enable Outgoing Stock Pickings', help='Show Outgoing Stock Pickings on Sale Invoice'
    )
    x_ksef_disable_shipping_third_party = fields.Boolean(
        string='KSeF Disable Shipping Address as Third Party',
        help='When enabled, the shipping address will not be automatically included as a third party '
             '(Podmiot3, role: Recipient) in KSeF XML for any sale invoice in this company.'
    )
    x_ksef_purchase_journal_id = fields.Many2one('account.journal', string='KSeF Purchase Journal')
    x_ksef_fallback_purchase_journal_id = fields.Many2one('account.journal', string='KSeF Fallback Purchase Journal')
    x_ksef_purchase_invoice_sync_date = fields.Datetime(string='KSeF Purchase Invoice Sync Date', copy=False)

    x_ksef_token = fields.Char(string='KSeF Encrypted Token', copy=False)
    x_ksef_plain_token = fields.Char(
        string='X KSeF Token',
        compute='_x_ksef_compute_plain_token',
        inverse='_x_ksef_inverse_plain_token',
        compute_sudo=True,
    )

    x_ksef_verification_link_certificate_datas = fields.Binary(
        string='KSeF Encrypted Verification Link Certificate', attachment=False, copy=False
    )
    x_ksef_plain_verification_link_certificate_datas = fields.Binary(
        string='KSeF Verification Link Certificate',
        compute='_x_ksef_compute_plain_verification_link_certificate_datas',
        inverse='_x_ksef_inverse_plain_verification_link_certificate_datas',
        compute_sudo=True,
    )

    x_ksef_verification_link_certificate_name = fields.Char(
        string='KSeF Verification Link Certificate Filename',
        copy=False,
    )

    x_ksef_verification_link_private_key_datas = fields.Binary(
        string='KSeF Encrypted Verification Link Private Key',
        attachment=False,
        copy=False,
    )
    x_ksef_plain_verification_link_private_key_datas = fields.Binary(
        string='KSeF Verification Link Private Key',
        compute='_x_ksef_compute_plain_verification_link_private_key_datas',
        inverse='_x_ksef_inverse_plain_verification_link_private_key_datas',
        compute_sudo=True,
    )

    x_ksef_verification_link_private_key_name = fields.Char(
        string='KSeF Verification Link Private Key Filename',
        copy=False,
    )

    x_ksef_verification_link_private_key_password = fields.Char(
        string='KSeF Encrypted Verification Link Private Key Password',
        copy=False,
    )
    x_ksef_plain_verification_link_private_key_password = fields.Char(
        string='KSeF Verification Link Private Key Password',
        compute='_x_ksef_compute_plain_verification_link_private_key_password',
        inverse='_x_ksef_inverse_plain_verification_link_private_key_password',
        compute_sudo=True,
    )

    @api.model
    def _x_ksef_get_secret_cipher(self):
        return Fernet(self.env['ir.config_parameter'].get_param(ENC_KEY).encode())

    @api.model
    def _x_ksef_secret_encrypt(self, value):
        cipher = self._x_ksef_get_secret_cipher()

        if isinstance(value, str):
            return cipher.encrypt(value.encode()).hex()

        else:
            return cipher.encrypt(value)

    @api.model
    def _x_ksef_secret_decrypt(self, value):
        cipher = self._x_ksef_get_secret_cipher()

        if isinstance(value, str):
            return cipher.decrypt(bytes.fromhex(value)).decode()

        else:
            return cipher.decrypt(value)

    def _x_ksef_compute_plain_secret(self, *, encrypted_field_name, plain_field_name):
        for company_id in self:
            company_id[plain_field_name] = company_id[encrypted_field_name] and company_id._x_ksef_secret_decrypt(
                company_id[encrypted_field_name]
            )

    def _x_ksef_inverse_plain_secret(self, *, encrypted_field_name, plain_field_name):
        for company_id in self:
            company_id[encrypted_field_name] = company_id[plain_field_name] and company_id._x_ksef_secret_encrypt(
                company_id[plain_field_name]
            )

    def _x_ksef_compute_plain_token(self):
        self._x_ksef_compute_plain_secret(encrypted_field_name='x_ksef_token', plain_field_name='x_ksef_plain_token')

    def _x_ksef_inverse_plain_token(self):
        self._x_ksef_inverse_plain_secret(encrypted_field_name='x_ksef_token', plain_field_name='x_ksef_plain_token')

    def _x_ksef_compute_plain_verification_link_private_key_password(self):
        self._x_ksef_compute_plain_secret(
            encrypted_field_name='x_ksef_verification_link_private_key_password',
            plain_field_name='x_ksef_plain_verification_link_private_key_password',
        )

    def _x_ksef_inverse_plain_verification_link_private_key_password(self):
        self._x_ksef_inverse_plain_secret(
            encrypted_field_name='x_ksef_verification_link_private_key_password',
            plain_field_name='x_ksef_plain_verification_link_private_key_password',
        )

    def _x_ksef_compute_plain_verification_link_private_key_datas(self):
        self._x_ksef_compute_plain_secret(
            encrypted_field_name='x_ksef_verification_link_private_key_datas',
            plain_field_name='x_ksef_plain_verification_link_private_key_datas',
        )

    def _x_ksef_inverse_plain_verification_link_private_key_datas(self):
        self._x_ksef_inverse_plain_secret(
            encrypted_field_name='x_ksef_verification_link_private_key_datas',
            plain_field_name='x_ksef_plain_verification_link_private_key_datas',
        )

    def _x_ksef_compute_plain_verification_link_certificate_datas(self):
        self._x_ksef_compute_plain_secret(
            encrypted_field_name='x_ksef_verification_link_certificate_datas',
            plain_field_name='x_ksef_plain_verification_link_certificate_datas',
        )

    def _x_ksef_inverse_plain_verification_link_certificate_datas(self):
        self._x_ksef_inverse_plain_secret(
            encrypted_field_name='x_ksef_verification_link_certificate_datas',
            plain_field_name='x_ksef_plain_verification_link_certificate_datas',
        )

    def x_ksef_get_client(self):
        self.ensure_one()

        return KsefClient(
            base_url=self.x_ksef_settings_id.endpoint_url,
            ksef_token=self.x_ksef_plain_token,
            public_asymmetric_key_path=self.x_ksef_settings_id.public_asymmetric_key_id.x_full_path,
            public_symmetric_key_path=self.x_ksef_settings_id.public_symmetric_key_id.x_full_path,
            nip_identifier=self.partner_id.x_get_pl_vat(raise_exception=True),
        )

    def x_ksef_notify_admins(self, note, subject=None):
        self.ensure_one()

        with Registry(self._cr.dbname).cursor() as cr:
            env = api.Environment(cr, self.env.uid, self.env.context)
            env.ref('trilab_ksef.ksef_channel').sudo().message_post(
                body=note,
                subject=subject,
                author_id=env.ref('base.partner_root').id,
            )

    def _x_ksef_set_auth_state(self, auth_state_key: str, value: str) -> None:
        try:
            with self.env.cr.savepoint():
                self.env['ir.config_parameter'].sudo().set_param(auth_state_key, value)
        except psycopg2.DatabaseError:
            _logger.warning(
                f'KSeF: failed to persist auth state {auth_state_key} for company {self.id} will re-authenticate on next call',
                self.id,
                exc_info=True,
            )

    def _x_ksef_get_authenticated_client(self):
        self.ensure_one()

        client = self.sudo().x_ksef_get_client()

        auth_state_key = f'x_ksef_{self.id}_auth_state'
        icp_id = self.env['ir.config_parameter'].sudo()

        if not (current_auth_state := icp_id.get_param(auth_state_key)):
            _logger.debug('No existing KSeF auth state found, authenticating...')
            auth_response = client.authenticate_ksef_token()
            self._x_ksef_set_auth_state(auth_state_key, auth_response.to_json())
            return client

        current_auth_state = json.loads(current_auth_state)
        now = (datetime.now() - timedelta(minutes=1)).timestamp()
        access_token_expired = current_auth_state.get('access_token_valid_until', -1) < now
        refresh_token_expired = current_auth_state.get('refresh_token_valid_until', -1) < now
        has_refresh_token = bool(current_auth_state.get('refresh_token'))

        if not access_token_expired:
            _logger.debug('Existing KSeF access token is valid, using it...')
            client.access_token = current_auth_state['access_token']
            return client

        elif access_token_expired and not refresh_token_expired and has_refresh_token:
            _logger.debug('Access token expired, refreshing with valid refresh token...')
            refresh_token = current_auth_state['refresh_token']

            refresh_response = client.refresh_token(refresh_token)
            client.access_token = refresh_response['accessToken']['token']

            self._x_ksef_set_auth_state(
                auth_state_key,
                json.dumps(
                    {
                        'access_token': client.access_token,
                        'access_token_valid_until': client.parse_datetime(
                            refresh_response['accessToken']['validUntil']
                        ).timestamp(),
                    }
                ),
            )
            return client

        if refresh_token_expired:
            _logger.debug('Both tokens expired, re-authenticating...')

        else:
            _logger.warning('Auth state corrupted (missing refresh_token), re-authenticating...')

        auth_response = client.authenticate_ksef_token()
        self._x_ksef_set_auth_state(auth_state_key, auth_response.to_json())

        return client

    def x_ksef_get_authenticated_client(self):
        self.ensure_one()

        try:
            return self._x_ksef_get_authenticated_client()

        except KsefAuthenticationStatusError as error:
            error_msg = _('KSeF Authentication Failed: [%s] %s', error.status_code, error.status_description)
            self.x_ksef_notify_admins(error_msg)
            raise UserError(error_msg) from error

        except KsefClientError as error:
            error_msg = _('KSeF Authentication Failed unexpectedly: %s', str(error))
            self.x_ksef_notify_admins(error_msg)
            raise UserError(error_msg) from error
