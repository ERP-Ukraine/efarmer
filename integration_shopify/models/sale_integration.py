#  See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, models, fields, SUPERUSER_ID, _
from odoo.tools import ormcache, SQL
from odoo.exceptions import UserError, ValidationError
from odoo.addons.integration.tools import expose_for_testing

from ..shopify_api import ShopifyAPIClient, SHOPIFY
from ..shopify.connection import _SHOPIFY_BATCH_LIMIT


_logger = logging.getLogger(__name__)


class SaleIntegration(models.Model):
    _inherit = 'sale.integration'

    type_api = fields.Selection(
        selection_add=[(SHOPIFY, 'Shopify')],
        ondelete={
            SHOPIFY: 'cascade',
        },
    )

    use_customer_currency = fields.Boolean(
        string='Import Orders in Customer Currency',
        copy=False,
        help=(
            'Check this option to ensure that imported orders is recorded using the customer\'s '
            'currency, preserving the original currency used during the sale.'
        ),
    )

    order_metafield_mapping_ids = fields.One2many(
        comodel_name='integration.metafield.mapping',
        inverse_name='integration_id',
        string='Order Metafield Mappings',
        domain=[('type', '=', 'order')],
        help=(
            'Defines the mappings between the order metafields in the external system and the '
            'fields in Odoo.'
        ),
    )

    customer_metafield_mapping_ids = fields.One2many(
        comodel_name='integration.metafield.mapping',
        inverse_name='integration_id',
        string='Customer Metafield Mappings',
        domain=[('type', '=', 'customer')],
        help=(
            ' Defines the mappings between the customer metafields in the external system and the '
            'fields in Odoo.'
        ),
    )

    invalid_location_mapping = fields.Boolean(
        string='Invalid Location Mapping',
        compute='_compute_invalid_location_mapping',
    )

    integration_channel_ids = fields.Many2many(
        comodel_name='external.sale.channel',
        string='Sale Channels',
        domain='[("integration_id", "=", id)]',
        help=(
            'Select the sales channels you want to import orders from in this e-commerce store. '
            'Leave this field empty if you want to import orders from all sales channels. '
            'A special "No Channel" option is available to include orders that are not associated '
            'with any specific sales channel. This can be useful for capturing orders that may have '
            'been created outside of the normal channel structure.'
        ),
    )

    shopify_customer_language = fields.Selection(
        selection=lambda self: self.env['res.lang'].get_installed(),
        string='Default Customer Language',
        help=(
            'Select the default language for partners. '
            'This language will be used when creating new partners in Odoo.'
        ),
    )

    translations_sync = fields.Boolean(  # Use the "is_translations_needed()" method instead
        string='Translations Synchronization',
        help=(
            'Select this option to enable the synchronization of translations '
        ),
    )

    catalog_line_ids = fields.One2many(
        comodel_name='integration.catalog.external.line',
        inverse_name='integration_id',
        string='Catalog Lines',
    )

    enable_webhook_hmac_validation = fields.Boolean(
        string='Enable Webhook HMAC Validation',
        default=True,
        help=(
            'When enabled, all incoming webhooks from Shopify will be verified using HMAC-SHA256 '
            'signature. Disable only temporarily if you experience validation issues after '
            'rotating your API secret key. Shopify may take up to 1 hour to start signing '
            'webhooks with a new secret after rotation.'
        ),
    )

    def is_shopify(self):
        self.ensure_one()
        return self.type_api == SHOPIFY

    @api.depends('location_line_ids')
    def _compute_invalid_location_mapping(self):
        for rec in self:
            if rec.is_integration_shopify:
                value = len(rec.location_line_ids.mapped('warehouse_id')) < len(rec.location_line_ids)
            else:
                value = False

            rec.invalid_location_mapping = value

    @expose_for_testing('Import Tags')
    def integration_api_import_tags(self, *args, **kw):
        if not self.is_integration_shopify:
            raise NotImplementedError

        tag_list = self.adapter.get_tags()

        Tag = self.env['external.integration.tag']
        tags = Tag.browse()

        for name in tag_list:
            tags |= Tag._get_or_create_external_tag(name, 'product')

        return tags

    def is_translations_needed(self, force_import: bool = None, force_export: bool = None):
        self.ensure_one()

        if self.is_integration_shopify:
            add_domain = []

            if force_import is not None:
                if not force_import:
                    add_domain.append(('import_enabled', '=', True))

            if force_export is not None:
                if not force_export:
                    add_domain.append(('export_enabled', '=', True))

            return (
                self.translations_sync
                and self.env['integration.res.lang.mapping'].has_more_than_one_mapping(self.id)
                and self.env['product.ecommerce.field.mapping'].has_translatable_fields(self.id, add_domain)
            )

        return super().is_translations_needed(
            force_import=force_import,
            force_export=force_export,
        )

    def is_integration_cancel_allowed(self):
        if len(self) == 1 and self.is_integration_shopify:
            return True
        return super().is_integration_cancel_allowed()

    def _get_cancel_order_view_id(self):
        if self.is_integration_shopify:
            return self.env.ref('integration_shopify.sale_order_cancel_integration_shopify_view_form').id
        return super()._get_cancel_order_view_id()

    def _set_default_template_reference_id(self):
        if self.is_shopify():
            self.template_reference_id = self.env.ref(
                'integration_shopify.shopify_template_reference_private').id
            return bool(self.template_reference_id)
        return super()._set_default_template_reference_id()

    def _set_default_product_reference_id(self):
        if self.is_shopify():
            self.product_reference_id = self.env.ref(
                'integration_shopify.shopify_ecommerce_field_variant_default_code').id
            return bool(self.product_reference_id)
        return super()._set_default_product_reference_id()

    def _set_default_template_barcode_id(self):
        if self.is_shopify():
            self.template_barcode_id = self.env.ref(
                'integration_shopify.shopify_template_barcode_private').id
            return bool(self.template_barcode_id)
        return super()._set_default_template_barcode_id()

    def _set_default_product_barcode_id(self):
        if self.is_shopify():
            self.product_barcode_id = self.env.ref(
                'integration_shopify.shopify_ecommerce_field_variant_barcode').id
            return bool(self.product_barcode_id)
        return super()._set_default_product_barcode_id()

    def _get_integration_auth_action(self, add_default_context: bool = True) -> dict:
        if self.is_integration_shopify:
            action = self.env.ref('integration_shopify.action_view_shopify_integration_authentication').read()[0]

            if add_default_context:
                action['context'] = {
                    'default_integration_id': self.id,
                    'default_url': self.get_settings_value('url'),
                    'default_key': self.get_settings_value('key'),
                    'default_use_oauth': self.get_settings_value('use_oauth'),
                    'default_client_id': self.get_settings_value('client_id'),
                    'default_secret_key': self.get_settings_value('secret_key'),
                    'default_access_granted': self.get_settings_value('access_granted'),
                }

            return action

        return super()._get_integration_auth_action()

    def get_class(self):
        self.ensure_one()

        if self.is_shopify():
            return ShopifyAPIClient

        return super(SaleIntegration, self).get_class()

    def _update_crons_activity(self):
        super()._update_crons_activity()

        for rec in self.filtered(lambda x: x.is_integration_shopify):
            if not rec.export_prices_cron_id:
                rec._create_sync_shopify_prices_cron()

    def _update_cron_names(self):
        super()._update_cron_names()

        for rec in self.filtered(lambda x: x.is_integration_shopify):
            if rec.export_prices_cron_id:
                rec.export_prices_cron_id.sudo().name = rec._get_cron_name('Sync Shopify Prices')

    def _create_sync_shopify_prices_cron(self):
        cron = self.sudo().env['ir.cron'].create({
            'active': False,
            'name': self._get_cron_name('Sync Shopify Prices'),
            'model_id': self.env.ref('integration.model_sale_integration').id,
            'interval_type': 'days',
            'interval_number': 1,
            'code': f'model.browse({self.id}).cron_calculation_and_export_prices()',
            'user_id': SUPERUSER_ID,
        })
        self.with_context(skip_write_actions=True).export_prices_cron_id = cron.id

    def cron_calculation_and_export_prices(self):
        """
        Calculate prices for all mapped products"""
        self.ensure_one()

        if not self.is_integration_shopify:
            return super().cron_calculation_and_export_prices()

        # 1. Remove old calculations with sql query
        self._unlink_product_pricelist_batches()

        # 3. Calculate prices for each pricelist-line
        for rec in self.catalog_line_ids:
            rec.create_price_batches_with_delay()

        return True

    def _unlink_product_pricelist_batches(self):
        return self.env['integration.product.pricelist.batch'].search([
            ('integration_id', '=', self.id),
            ('state', 'in', ['done', 'cancelled', False, '']),
        ]).unlink()

    def _get_pairs_of_external_and_odoo_products(self):
        self.env.cr.execute(SQL("""
            SELECT
                ippe.code,
                ippm.product_id
            FROM integration_product_product_external AS ippe
            JOIN integration_product_product_mapping AS ippm
                ON ippe.id = ippm.external_product_id
                AND ippe.integration_id = %(integration_id)s
                AND ippm.integration_id = %(integration_id)s
            JOIN product_product AS pp
                ON ippm.product_id = pp.id
        """, integration_id=self.id))

        return self.env.cr.fetchall() or []

    def to_dictionary(self):
        result = super(SaleIntegration, self).to_dictionary()

        if self.is_integration_shopify:
            result.update(
                debug_mode=bool(self.get_settings_value('debug_mode')),
                graphql_version=self._get_graphql_version(),
                use_customer_currency=self.use_customer_currency,
            )

        return result

    @ormcache()
    def _get_graphql_version(self):
        return self.env['ir.config_parameter'].sudo().get_param('integration.graphql_version')

    def get_external_block_limit(self):
        if self.is_integration_shopify:
            return _SHOPIFY_BATCH_LIMIT
        return super(SaleIntegration, self).get_external_block_limit()

    @expose_for_testing('Fetch Shopify Catalogs')
    def fetch_shopify_catalogs(self):
        if not self.is_integration_shopify:
            return

        data_list = self.adapter.get_catalogs()

        catalogs = self.env['integration.catalog.external']
        for data in data_list:
            catalogs |= catalogs.browse().create_or_update(self.id, data)

        return catalogs

    def export_sale_order_status(self, order):
        res = super(SaleIntegration, self).export_sale_order_status(order)

        if not res or not self.is_integration_shopify:
            return res

        vals = order._prepare_vals_for_sale_order_status()

        if vals['status'] == 'paid':
            res['internal_status'] = 'done'
            order._apply_values_from_external({'payment_transactions': [res]})

        return res

    def export_tracking(self, pickings):
        """Redefined method in order to apply external fulfillments"""
        res = super(SaleIntegration, self).export_tracking(pickings)
        if not self.is_integration_shopify:
            return res

        if res:
            order = pickings.mapped('sale_id')
            order._apply_values_from_external({'order_fulfillments': res})
            order.external_fulfillment_ids.mark_done()

        return res

    def _ensure_settings(self):
        if self.is_integration_shopify:
            self._ensure_not_null_setting(['url', 'key'])

        return super()._ensure_settings()

    def advanced_inventory(self):
        if self.is_integration_shopify:
            return True
        return super(SaleIntegration, self).advanced_inventory()

    def is_importable_order_status(self, statuses: list[str]) -> bool:
        if not self.is_integration_shopify:
            return super().is_importable_order_status(statuses)

        # TODO: add filtering by sale channel
        financial_status, fulfillment_status = statuses
        financial_status_ok = fulfillment_status_ok = False

        fin_state_list, fulf_state_list = self.get_importable_order_statuses()

        if financial_status in fin_state_list:
            financial_status_ok = True

        if fulfillment_status in fulf_state_list:
            fulfillment_status_ok = True

        return (financial_status_ok and fulfillment_status_ok)

    def get_importable_order_statuses(self) -> tuple[list[str], list[str]]:
        if not self.is_integration_shopify:
            return super().get_importable_order_statuses()

        financial_statuses = self.get_settings_value('receive_order_financial_statuses') or ''
        fulfillment_statuses = self.get_settings_value('receive_order_fulfillment_statuses') or ''

        financial_statuses_list = [s.strip() for s in financial_statuses.split(',') if s.strip()]
        fulfillment_statuses_list = [s.strip() for s in fulfillment_statuses.split(',') if s.strip()]

        if not financial_statuses_list:
            raise ValidationError(
                _('Invalid configuration: Financial status filter is not configured. '
                  'Please configure "Order financial statuses" in the integration settings.')
            )

        if not fulfillment_statuses_list:
            raise ValidationError(
                _('Invalid configuration: Fulfillment status filter is not configured. '
                  'Please configure "Order fulfillment statuses" in the integration settings.')
            )

        return (financial_statuses_list, fulfillment_statuses_list)

    def _handle_mapping_data(self, template_id: int, t_mapping: dict, v_mapping_list: list) -> tuple:
        result = super(SaleIntegration, self) \
            ._handle_mapping_data(template_id, t_mapping, v_mapping_list)

        if self.is_integration_shopify:
            # 1. Create attributes mappings
            options = t_mapping['attribites_data']['formatted_options']
            if options:
                external_attribute_ids, __ = self._import_external(
                    'integration.product.attribute.external',
                    '',
                    external_data=options,
                )
                external_attribute_ids._map_external(options)

            # 2. Create attribute-values mappings
            option_values = t_mapping['attribites_data']['formatted_option_values']
            if option_values:
                external_attribute_value_ids, __ = self._import_external(
                    'integration.product.attribute.value.external',
                    '',
                    external_data=option_values,
                )
                external_attribute_value_ids._map_external(option_values)

        return result

    def _retrieve_webhook_routes(self):
        if self.is_integration_shopify:
            return {
                'orders': [
                    ('Order Create', 'ORDERS_CREATE'),
                    ('Order Paid', 'ORDERS_PAID'),
                    ('Order Cancel', 'ORDERS_CANCELLED'),
                    ('Order Fullfill', 'ORDERS_FULFILLED'),
                    ('Order Partially Fullfill', 'ORDERS_PARTIALLY_FULFILLED'),
                ],
                'products': [
                    ('Product Create', 'PRODUCTS_CREATE'),
                    ('Products Update', 'PRODUCTS_UPDATE'),
                    ('Products Delete', 'PRODUCTS_DELETE'),
                ],
            }

        return super(SaleIntegration, self)._retrieve_webhook_routes()

    def _prepare_shopify_oauth_redirect_url(self):
        base_url = self._get_base_url_or_debug()
        return f'{base_url}/{self.env.cr.dbname}/integration/shopify/{self.id}/oauth'

    def force_set_inactive(self):
        if self.is_integration_shopify:
            return {'status': 'draft'}
        return super(SaleIntegration, self).force_set_inactive()

    def _get_error_webhook_message(self, error):
        if not self.is_integration_shopify:
            return super(SaleIntegration, self)._get_error_webhook_message(error)

        return _('Shopify Webhook Error: %s') % error.args[0]

    def _get_weight_integration_fields(self):
        if not self.is_integration_shopify:
            return super(SaleIntegration, self)._get_weight_integration_fields()

        return [
            'integration_shopify.shopify_ecommerce_field_variant_weight',
        ]

    def import_metafields(self):
        """
        Update metafields associated with customers from the external system (e.g., Shopify).
        """
        if not self.is_integration_shopify:
            return False

        meta_type = self.env.context.get('external_entity')
        if not meta_type:
            raise UserError(_(
                'Missing required context variable: "external_entity". This is a technical error. '
                'Please contact our support team at https://support.ventor.tech/ if the issue persists'
            ))

        metafield_list = self.adapter.get_metafields(meta_type)

        if not metafield_list:
            return self._raise_notification(
                'warning',
                f'There are no {meta_type.title()} metafields in your Shopify store',
            )

        MetaField = self.env['external.metafield']
        actual_metafields = MetaField.browse()
        domain = [('integration_id', '=', self.id), ('type', '=', meta_type)]

        for data in metafield_list:
            record = MetaField.search([
                *domain,
                ('metafield_key', '=', data['metafield_key']),
                ('metafield_namespace', '=', data['metafield_namespace']),
            ])

            if record:
                record.write(data)
            else:
                record = MetaField.create({**{k: v for k, _, v in domain}, **data})

            actual_metafields |= record

        # Delete meta fields that don't exist in Shopify
        (MetaField.search(domain) - actual_metafields).unlink()

        return self._raise_notification(
            'success',
            _('%ss metafields were successfully updated') % meta_type.title(),
        )

    def import_sale_channels(self):
        """SaleChannel |=
        Import sales channels from Shopify.
        """
        SaleChannel = self.env['external.sale.channel']

        if not self.is_integration_shopify:
            return SaleChannel

        # 1. Fetch sales channels from Shopify
        data_list = self.adapter.get_sale_channels()

        # 2. Ensure 'No Channel' exists
        channels = SaleChannel._ensure_no_channel_exists(self.id)

        # 3. Create or update sales channels
        for data in data_list:
            channels |= SaleChannel.create_or_update(self.id, data['channel_id'], data['channel_name'])

        return channels

    def _filter_orders_shopify(self, external_orders_data_list: list):
        """
        General method to filter Shopify orders.
        This method will find and apply specific Shopify filtering methods.

        Args:
            external_orders_data_list (list): List of orders data.

        Returns:
            recordset: Recordset of filtered orders data.
        """

        filtered_orders = self._filter_orders_by_channels(external_orders_data_list)

        return filtered_orders

    def _filter_orders_by_channels(self, external_orders_data_list: list):
        """
        Filter orders by channel ID (publication ID).

        This method filters orders based on the integration channels configured.
        It handles the 'No Channel' case for orders without a specific channel.

        Args:
            external_orders_data_list (list): List of orders data.

        Returns:
            recordset: Recordset of filtered orders data.
        """

        channels = self.integration_channel_ids
        if not channels:
            return external_orders_data_list

        external_channel_ids = channels.mapped('external_id')

        # Include orders without a channel if 'No Channel' is selected
        include_no_channel = any(x.is_no_channel for x in channels)

        filtered_orders_data = []
        order = self.adapter.gql.Order

        for data in external_orders_data_list:
            order.set(**data['data'])
            channel_data = order.parse_sale_channel()

            if channel_data:
                if channel_data['channel_id'] in external_channel_ids:
                    filtered_orders_data.append(data)
            elif include_no_channel:
                filtered_orders_data.append(data)

            order.reset()

        filtered_count = len(external_orders_data_list) - len(filtered_orders_data)
        if filtered_count:
            _logger.info('%s: %s orders skipped by sales-channels.', self.name, filtered_count)

        return filtered_orders_data
