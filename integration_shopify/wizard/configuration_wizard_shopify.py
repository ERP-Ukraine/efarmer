#  See LICENSE file for full copyright and licensing details.

from shopify import ApiVersion

from odoo import models, fields, api
from odoo.exceptions import ValidationError


MIN_API_VERSION = 202204

REQUIRED_SCOPES = (
    'read_locations',
    'read_customers',
    'read_products',
    'write_products',
    'read_orders',
    'write_orders',
    'read_inventory',
    'write_inventory',
    'write_fulfillments',
    'read_fulfillments',
    'read_merchant_managed_fulfillment_orders',
    'write_merchant_managed_fulfillment_orders',
)


class ShopifyOrderStatus:
    """
    The class contains order statuses that can be used both for querying the store's API
    and for using them during order parsing. It's worth noting that they often have
    different names but mean the same thing. For example, the "shipped" status in a request
    will correspond to the "fulfilled" status in the response. Similarly, the "unshipped"
    or "unfulfilled" status in a request will correspond to "null" or "null + partial" statuses
    in the response.
    """

    STATUS_AUTHORIZED = 'authorized'
    STATUS_PENDING = 'pending'
    STATUS_PAID = 'paid'
    STATUS_PARTIALLY_PAID = 'partially_paid'
    STATUS_REFUNDED = 'refunded'
    STATUS_VOIDED = 'voided'
    STATUS_PARTIALLY_REFUNDED = 'partially_refunded'
    STATUS_UNPAID = 'unpaid'

    STATUS_PARTIAL = 'partial'
    STATUS_FULFILLED = 'fulfilled'
    STATUS_RESTOCKED = 'restocked'
    STATUS_UNSHIPPED = 'unshipped'
    STATUS_UNFULFILLED = 'unfulfilled'

    STATUS_OPEN = 'open'
    STATUS_CLOSED = 'closed'
    STATUS_CANCELLED = 'cancelled'

    SPECIAL_STATUS_ANY = 'any'
    SPECIAL_STATUS_SHIPPED = 'shipped'

    _financial_status_data = {
        STATUS_AUTHORIZED: (
            'Authorized',
            'The payments have been authorized.',
        ),
        STATUS_PENDING: (
            'Pending',
            'The payments are pending. Payment might fail in this state. '
            'Check again to confirm whether the payments have been paid successfully.',
        ),
        STATUS_PAID: (
            'Paid',
            'The payments have been paid.',
        ),
        STATUS_PARTIALLY_PAID: (
            'Partially Paid',
            'The order has been partially paid.',
        ),
        STATUS_REFUNDED: (
            'Refunded',
            'The payments have been refunded.',
        ),
        STATUS_VOIDED: (
            'Voided',
            'The payments have been voided.',
        ),
        STATUS_PARTIALLY_REFUNDED: (
            'Partially Refunded',
            'The payments have been partially refunded.',
        ),
        STATUS_UNPAID: (
            'Unpaid',
            'Receive authorized and partially paid orders.',
        ),
    }

    _fulfillment_status_data = {
        STATUS_FULFILLED: (  # !!! In Shopify API this parameter named as `shipped`
            'Shipped',  # howewer in received order it named `fulfilled` and we need to have the
            'Receive orders that have been shipped. '  # mapping object exactly as `fulfilled`
            'Returns orders with fulfillment_status of fulfilled.',
        ),
        STATUS_PARTIAL: (
            'Partial',
            'Receive partially shipped orders.'
        ),
        STATUS_UNSHIPPED: (
            'Unshipped',
            'Receive orders that have not yet been shipped. '
            'Returns orders with fulfillment_status of null.',
        ),
        STATUS_UNFULFILLED: (
            'Unfulfilled',
            'Receive orders with fulfillment_status of null or partial.',
        ),
    }

    _fulfillment_status_restocked_data = {
        STATUS_RESTOCKED: (
            'Restocked',
            'Every line item in the order has been restocked and the order canceled.',
        ),
    }

    _any_status_data = {
        SPECIAL_STATUS_ANY: (
            'Any',
            'Receive orders of any status.',
        ),
    }

    _order_status_data = {
        STATUS_OPEN: (
            'Open',
            'Receive only open orders.'
        ),
        STATUS_CLOSED: (
            'Closed',
            'Receive only closed orders.',
        ),
        STATUS_CANCELLED: (
            'Cancelled',
            'Receive only cancelled orders.',
        ),
    }

    @classmethod
    def order_statuses(cls):
        return {
            **cls._any_status_data,
            **cls._order_status_data,
        }

    @classmethod
    def financial_statuses(cls):
        return {
            **cls._any_status_data,
            **cls._financial_status_data,
        }

    @classmethod
    def fulfillment_statuses(cls):
        return {
            **cls._any_status_data,
            **cls._fulfillment_status_data,
        }

    @classmethod
    def all_statuses(cls):
        return {
            **cls._any_status_data,
            **cls._order_status_data,
            **cls._financial_status_data,
            **cls._fulfillment_status_data,
            **cls._fulfillment_status_restocked_data,
        }


class QuickConfigurationShopify(models.TransientModel):
    _name = 'configuration.wizard.shopify'
    _inherit = 'configuration.wizard'
    _description = 'Quick Configuration for Shopify'
    _steps = [
        ('step_url', 'Step 1. Enter Store Url, API version and Access Token'),
        ('step_access_scopes', 'Step 2. Admin API access scopes'),
        ('step_languages', 'Step 3. Languages Mapping'),
        ('step_order_status', 'Step 4. Select order statuses for the receive filter'),
        (
            'step_order_financial_status',
            'Step 5. Select order financial statuses for the receive filter',
        ),
        (
            'step_order_fulfillment_status',
            'Step 6. Select order fulfillment statuses for the receive filter',
        ),
        ('step_finish', 'Finish'),
    ]

    def _get_available_lib_versions(self):
        releases = ApiVersion.versions.values()
        versions = [
            x.name for x in releases if x.stable and int(x.numeric_version) >= MIN_API_VERSION
        ]
        return [(x, x) for x in versions]

    state = fields.Char(
        default='step_url',
    )
    url = fields.Char(
        string='Shop Url',
    )
    api_version = fields.Selection(
        selection=_get_available_lib_versions,
        string='API Version',
    )
    key = fields.Char(
        string='Admin API access token',
    )
    secret_key = fields.Char(
        string='API secret key',
    )
    is_valid_access_scopes = fields.Boolean(
        string='Proven Access Scopes',
        compute='_compute_is_valid_access_scopes',
    )
    configuration_scope_ids = fields.One2many(
        comodel_name='configuration.wizard.shopify.line',
        inverse_name='configuration_wizard_id',
        string='Access Scopes',
        domain=lambda self: [
            ('is_scope', '=', True),
            ('configuration_wizard_id', '=', self.id),
        ],
    )
    configuration_order_status_ids = fields.One2many(
        comodel_name='configuration.wizard.shopify.line',
        inverse_name='configuration_wizard_id',
        string='Order Statuses',
        domain=lambda self: [
            ('is_order_status', '=', True),
            ('configuration_wizard_id', '=', self.id),
        ],
    )
    configuration_order_financial_status_ids = fields.One2many(
        comodel_name='configuration.wizard.shopify.line',
        inverse_name='configuration_wizard_id',
        string='Order Financial Statuses',
        domain=lambda self: [
            ('is_order_financial_status', '=', True),
            ('configuration_wizard_id', '=', self.id),
        ],
    )
    configuration_order_fulfillment_status_ids = fields.One2many(
        comodel_name='configuration.wizard.shopify.line',
        inverse_name='configuration_wizard_id',
        string='Order Fulfillment Statuses',
        domain=lambda self: [
            ('is_order_fulfillment_status', '=', True),
            ('configuration_wizard_id', '=', self.id),
        ],
    )
    configuration_shopify_line_ids = fields.One2many(
        comodel_name='configuration.wizard.shopify.line',
        inverse_name='configuration_wizard_id',
        string='Configuration Shopify Lines',
        domain=lambda self: [
            ('configuration_wizard_id', '=', self.id),
        ],
    )

    @api.depends('configuration_scope_ids')
    def _compute_is_valid_access_scopes(self):
        for rec in self:
            value = True

            if rec.configuration_scope_ids:
                value = not any(rec.configuration_scope_ids.mapped('is_missed'))

            rec.is_valid_access_scopes = value

    # Step Url
    def run_before_step_url(self):
        self.url = self.integration_id.get_settings_value('url')
        current_version = self.integration_id.get_settings_value('version')

        versions = self.env['configuration.wizard.shopify']._get_available_lib_versions()
        available_versions = [x[0] for x in versions]

        if current_version not in available_versions:
            current_version = False

        self.api_version = current_version
        self.key = self.integration_id.get_settings_value('key')
        self.secret_key = self.integration_id.get_settings_value('secret_key')

    def run_after_step_url(self):
        self.integration_id.set_settings_value('url', self.url)
        self.integration_id.set_settings_value('version', self.api_version)
        self.integration_id.set_settings_value('key', self.key)
        self.integration_id.set_settings_value('secret_key', self.secret_key)

        self.integration_id.increment_sync_token()

        try:
            self.integration_id.action_active()
        except Exception as ex:
            raise ValidationError(ex.name)

        return True

    # Step Scopes
    def run_before_step_access_scopes(self):
        self._run_before_step_access_scopes()

    def _run_before_step_access_scopes(self):
        self.configuration_scope_ids.unlink()

        vals_list = list()
        adapter = self.integration_id._build_adapter()

        adapter_scopes = adapter._client._get_access_scope()
        adapter.access_scopes = adapter_scopes
        all_scopes = set([*adapter_scopes, *REQUIRED_SCOPES])

        for scope in all_scopes:
            if scope not in REQUIRED_SCOPES:
                continue

            vals = {
                'is_scope': True,
                'name': ' '.join(map(lambda x: x.capitalize(), scope.split('_'))),
                'is_missed': scope not in adapter_scopes,
                'configuration_wizard_id': self.id,
            }
            vals_list.append(vals)

        self.env['configuration.wizard.shopify.line'].create(vals_list)

    def run_after_step_access_scopes(self):
        return True

    # Step Order Status
    def run_before_step_order_status(self):
        if self.configuration_order_status_ids:
            return

        vals_list = list()
        status_dict = ShopifyOrderStatus.order_statuses()
        for code, (name, info) in status_dict.items():
            vals = {
                'is_order_status': True,
                'activate': False,
                'name': name,
                'code': code,
                'info': info,
                'configuration_wizard_id': self.id,
            }
            vals_list.append(vals)

        lines = self.env['configuration.wizard.shopify.line'].create(vals_list)

        existing_value = self.integration_id.get_settings_value(
            'receive_order_statuses',
        )
        if existing_value:
            status_list = existing_value.split(',')
            lines.filtered(lambda x: x.code in status_list).write({
                'activate': True,
            })

    def run_after_step_order_status(self):
        active_status_ids = self.configuration_order_status_ids.filtered('activate')
        default_status_id = self.configuration_order_status_ids.filtered(
            lambda x: x.code == ShopifyOrderStatus.STATUS_OPEN
        )
        status_ids = active_status_ids or default_status_id

        self.integration_id.set_settings_value(
            'receive_order_statuses',
            ','.join(status_ids.mapped('code')),
        )
        return True

    # Step Order Financial Status
    def run_before_step_order_financial_status(self):
        if self.configuration_order_financial_status_ids:
            return

        vals_list = list()
        status_dict = ShopifyOrderStatus.financial_statuses()
        for code, (name, info) in status_dict.items():
            vals = {
                'is_order_financial_status': True,
                'activate': False,
                'name': name,
                'code': code,
                'info': info,
                'configuration_wizard_id': self.id,
            }
            vals_list.append(vals)

        lines = self.env['configuration.wizard.shopify.line'].create(vals_list)

        existing_value = self.integration_id.get_settings_value(
            'receive_order_financial_statuses',
        )
        if existing_value:
            status_list = existing_value.split(',')
            lines.filtered(lambda x: x.code in status_list).write({
                'activate': True,
            })

    def run_after_step_order_financial_status(self):
        active_status_ids = self.configuration_order_financial_status_ids.filtered('activate')
        default_status_id = self.configuration_order_financial_status_ids.filtered(
            lambda x: x.code == ShopifyOrderStatus.SPECIAL_STATUS_ANY
        )
        status_ids = active_status_ids or default_status_id

        self.integration_id.set_settings_value(
            'receive_order_financial_statuses',
            ','.join(status_ids.mapped('code')),
        )
        return True

    # Step Order Fullfillment Status
    def run_before_step_order_fulfillment_status(self):
        if self.configuration_order_fulfillment_status_ids:
            return

        vals_list = list()
        status_dict = ShopifyOrderStatus.fulfillment_statuses()
        for code, (name, info) in status_dict.items():
            vals = {
                'is_order_fulfillment_status': True,
                'activate': False,
                'name': name,
                'code': code,
                'info': info,
                'configuration_wizard_id': self.id,
            }
            vals_list.append(vals)

        lines = self.env['configuration.wizard.shopify.line'].create(vals_list)

        existing_value = self.integration_id.get_settings_value(
            'receive_order_fulfillment_statuses',
        )
        if existing_value:
            status_list = existing_value.split(',')
            lines.filtered(lambda x: x.code in status_list).write({
                'activate': True,
            })

    def run_after_step_order_fulfillment_status(self):
        active_status_ids = self.configuration_order_fulfillment_status_ids.filtered('activate')
        default_status_id = self.configuration_order_fulfillment_status_ids.filtered(
            lambda x: x.code == ShopifyOrderStatus.SPECIAL_STATUS_ANY
        )
        status_ids = active_status_ids or default_status_id

        self.integration_id.set_settings_value(
            'receive_order_fulfillment_statuses',
            ','.join(status_ids.mapped('code')),
        )
        return True

    def refresh_scopes(self):
        self._run_before_step_access_scopes()
        return self.get_action_view()

    @staticmethod
    def get_form_xml_id():
        return 'integration_shopify.view_configuration_wizard'


class QuickConfigurationShopifyLine(models.TransientModel):
    _name = 'configuration.wizard.shopify.line'
    _description = 'Quick Configuration Shopify Line'

    activate = fields.Boolean(
        string='Activate',
    )
    name = fields.Char(
        string='Name',
    )
    code = fields.Char(
        string='Code',
    )
    info = fields.Char(
        string='Info',
    )
    is_scope = fields.Boolean(
        string='Is Scope',
    )
    is_missed = fields.Boolean(
        string='Missed',
    )
    is_order_status = fields.Boolean(
        string='Is Order Status',
    )
    is_order_financial_status = fields.Boolean(
        string='Is Order Financial Status',
    )
    is_order_fulfillment_status = fields.Boolean(
        string='Is Order Fullfillment Status',
    )
    configuration_wizard_id = fields.Many2one(
        comodel_name='configuration.wizard.shopify',
        ondelete='cascade',
    )
