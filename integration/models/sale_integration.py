# See LICENSE file for full copyright and licensing details.

import binascii
import os
import json
import logging
import pytz
import traceback

from datetime import datetime, timedelta
from dateutil import parser
from collections import defaultdict
from io import StringIO
from psycopg2 import OperationalError, IntegrityError
from time import time
from typing import List, Dict

from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.exceptions import UserError, ValidationError
from odoo.modules.registry import Registry
from odoo.tools import config, ormcache, float_is_zero
from odoo.tools.safe_eval import safe_eval
from odoo.tools.misc import clean_context

from odoo.addons.integration.exceptions import NoExternal
from odoo.addons.integration_queue_job.job import Job

from ..api.no_api import NoAPIClient
from ..exceptions import ErrorStore as es
from ..tools import (
    expose_for_testing,
    normalize_uom_name,
    pluralize,
    raise_requeue_job_on_concurrent_update,
    track_changes,
    _is_valid_email,
    HtmlWrapper,
    Adapter,
    AdapterHub,
    PriceList,
    TemplateHub,
)


API_KEY_SIZE = 20  # in bytes
INTEGRATION_MODULES = [
    'integration',
    'integration_shopify',
    'integration_prestashop',
    'integration_magento2',
    'integration_woocommerce',
    'integration_queue_job',
    'queue_job'
]

DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'
EXCLUDED_MAPPING_MODELS = [
    'integration.account.tax.group.mapping',
    'integration.metafield.mapping',
    'integration.ecommerce.product.image.mapping',
]
LOG_SEPARATOR = '================================'
IMPORT_EXTERNAL_BLOCK = 150  # Don't make more, because of 414 Request-URI Too Large error
EXPORT_EXTERNAL_BLOCK = 500

IMAGE_FIELDS = ['image_1920', 'integration_template_image_ids', 'integration_variant_image_ids']
PRODUCT_QTY_FIELDS = ['free_qty', 'qty_available', 'virtual_available']
TRACKED_FIELDS_INITIAL_PRODUCT_EXPORT = ['integration_ids']
SEARCH_CUSTOMER_FIELDS = ['email', 'name', 'phone']
INVENTORY_DEPENDENT_FIELDS = {
    'update_stock_for_manufacture_boms',
    'export_inventory_job_enabled',
    'inventory_synchronization_cron_id_active'
}

_logger = logging.getLogger(__name__)


class SaleIntegration(models.Model):
    _name = 'sale.integration'
    _description = 'E-Commerce Store'
    _inherit = ['mail.thread']

    _unique_name = models.Constraint(
        'unique(name)',
        'A record with the same name already exists.',
    )
    _order_name_ref_unique = models.Constraint(
        'unique(order_name_ref)',
        'Sale Order prefix name should be unique.',
    )

    _adapter_hub_ = AdapterHub()

    name = fields.Char(
        string='Name',
        required=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )
    integration_lang_id = fields.Many2one(
        comodel_name='res.lang',
        string='Default Odoo Language for E-Commerce Store',
        help=(
            'Choose the default Odoo language for this e-commerce store, which will be applied '
            'during import and export processes. Typically, this should align with the '
            'language used in the e-commerce system for consistency.'
        ),
    )
    lang_ids = fields.Many2many(
        comodel_name='res.lang',
        compute='_compute_lang_ids',
        string='Mapped Languages',
    )
    type_api = fields.Selection(
        selection=[('no_api', 'Not Use API')],
        string='API Service',
        required=True,
        ondelete={
            'no_api': 'cascade',
        },
        help=(
            'Select the API service type for the current Sales Integration. '
            'This setting should be configured initially and must remain unchanged '
            'after the initial setup to ensure proper integration functionality.'
        ),
    )
    state = fields.Selection(
        selection=[
            ('new', 'New'),
            ('draft', 'Draft'),
            ('active', 'Active'),
        ],
        string='Status',
        required=True,
        default='new',
    )
    field_ids = fields.One2many(
        comodel_name='sale.integration.api.field',
        inverse_name='sia_id',
        string='Fields',
    )
    test_method = fields.Selection(
        selection='_get_test_method',
        string='Execute Method (Debug)',
        help=(
            'Specify the method you wish to execute for testing purposes. Caution: Running '
            'test methods directly can alter your data and system behavior. This should only '
            'be done by users who understand the implications and have ensured that it is '
            'safe to proceed.'
        ),
    )

    test_method_parameter = fields.Char(
        string='Test Method Parameter',
    )

    location_line_ids = fields.One2many(
        comodel_name='external.stock.location.line',
        inverse_name='integration_id',
        string='Locations',
    )
    location_ids = fields.Many2many(  # TODO: Deprecated. Drop it after 1.12.0 integration release.
        comodel_name='stock.location',
        string='Depreceted Locations',
        domain=[
            ('usage', '=', 'internal'),
        ],
    )
    last_receive_orders_datetime = fields.Datetime(
        string='Last Receive Orders Time',
        required=True,
        default=fields.Datetime.now,
        help=(
            'Sets the import filter based on the order update time from the E-Commerce system. '
            'The "Last Receive Orders Time" is automatically updated after each order import '
            'into Odoo, ensuring only new updates are fetched.'
        ),
    )
    last_receive_orders_datetime_str = fields.Char(
        compute='_compute_last_receive_orders_datetime_str',
        string='Last Receive Orders Time String',
    )
    last_order_sync_datetime = fields.Datetime(
        string='Last Order Sync Time',
        help='The actual time when the last order synchronization was performed.',
    )
    last_update_pricelist_items = fields.Datetime(
        string='Pricelist Last Sync Date',
        default=fields.Datetime.now,
        help=(
            'This timestamp indicates the last update for pricelist items. '
            'Only items modified after this date will be selected for export to ensure '
            'the synchronization includes the most recent changes.'
        ),
    )
    receive_orders_cron_id = fields.Many2one(
        comodel_name='ir.cron',
    )
    receive_orders_cron_id_active = fields.Boolean(
        string='Enable Order Import',
        related='receive_orders_cron_id.active',
        readonly=False,
        help=(
            'Enable this option to import orders from the connected E-Commerce System. '
            'Orders will only be imported when this option is enabled AND the integration is active.'
        ),
    )
    export_template_job_enabled = fields.Boolean(
        string='Enable Product Template Export Job',
        default=False,
        help=(
            'Check this option to activate the automatic export of product templates to the '
            'e-commerce system whenever relevant product fields are updated in Odoo.'
        ),
    )
    export_inventory_job_enabled = fields.Boolean(
        string='Real-Time Inventory Updates',
        default=False,
        help=(
            'Check this box to enable immediate synchronization of inventory levels to the '
            'e-commerce system following any stock changes in Odoo. This ensures your e-commerce '
            'platform reflects the most current stock information.'
        ),
    )
    inventory_synchronization_cron_id = fields.Many2one(
        comodel_name='ir.cron',
        string='Inventory Synchronization Cron',
    )
    inventory_synchronization_cron_id_active = fields.Boolean(
        string='Scheduled Inventory Sync',
        related='inventory_synchronization_cron_id.active',
        readonly=False,
        help=(
            'Enable this to schedule periodic inventory updates from Odoo to the e-commerce '
            'system. This is done via a cron job that runs at intervals set by you, '
            'ideal for batch updating stock levels.'
        ),
    )
    next_inventory_synchronization_date = fields.Datetime(
        string='Next Synchronization Date',
        compute='_compute_next_inventory_synchronization_date',
        readonly=False,
        inverse='_inverse_next_inventory_synchronization_date',
    )
    export_tracking_job_enabled = fields.Boolean(
        string='Enable Order Tracking Export Job',
        default=False,
        help=(
            'Check this option to automate the export of tracking numbers from Odoo to the '
            'e-commerce platform upon confirmation of the delivery order.'
        ),
    )
    export_sale_order_status_job_enabled = fields.Boolean(
        string='Enable Sale Order Status Export Job',
        default=False,
        help=(
            'Check this option to automatically update the sale order status on the '
            'e-commerce system corresponding to status changes in Odoo.'
        ),
    )
    product_ids = fields.Many2many(
        'product.template', 'sale_integration_product', 'sale_integration_id', 'product_id',
        'Products',
        copy=False,
        check_company=True,
    )

    discount_product_id = fields.Many2one(
        comodel_name='product.product',
        string='Discount Product',
        domain="[('type', '=', 'service')]",
        help=(
            'Select a product to represent discounts as a separate line item within Odoo. '
            'This will ensure that discounts are itemized clearly on sales orders.'
        ),
    )

    positive_price_difference_product_id = fields.Many2one(
        comodel_name='product.product',
        string='Price Difference Product (Positive)',
        domain="[('type', '=', 'service')]",
        help=(
            'Select a product to account for any positive discrepancies between the '
            'total amounts of orders in the E-Commerce system and Odoo. This product will be '
            'added to the sales order as a separate line to adjust for the price difference.'
        ),
    )

    negative_price_difference_product_id = fields.Many2one(
        comodel_name='product.product',
        string='Price Difference Product (Negative)',
        domain="[('type', '=', 'service')]",
        help=(
            'Select a product to account for any negative discrepancies between the '
            'total amounts of orders in the E-Commerce system and Odoo. This product will be '
            'added to the sales order as a separate line to adjust for the price difference.'
        ),
    )

    gift_wrapping_product_id = fields.Many2one(
        comodel_name='product.product',
        string='Gift Wrapping Product',
        help=(
            'Select a specific product to be used for gift-wrapping services. If a sales order '
            'in PrestaShop includes gift wrapping, this product will be added accordingly.'
        ),
    )

    run_action_on_cancel_so = fields.Boolean(
        string='Sync Cancelled SO Status',
        copy=False,
        help=(
            'Enable this option to automatically update the order status in the e-commerce '
            'system when a sales order is cancelled in Odoo.'
        ),
    )

    sub_status_cancel_id = fields.Many2one(
        comodel_name='sale.order.sub.status',
        string='Store Order Status for Cancelled SO',
        domain='[("integration_id", "=", id)]',
        copy=False,
        help=(
            'Specify the store order status that will be sent to the e-commerce system when '
            'a sales order is cancelled in Odoo.'
        ),
    )

    run_action_on_shipping_so = fields.Boolean(
        string='Sync Shipped SO Status',
        copy=False,
        help=(
            'Activate this option to update the order status in the e-commerce system '
            'automatically when a sales order is marked as shipped in Odoo.'
        ),
    )

    sub_status_shipped_id = fields.Many2one(
        comodel_name='sale.order.sub.status',
        string='Store Order Status for Shipped SO',
        domain='[("integration_id", "=", id)]',
        copy=False,
        help=(
            'Specify the store order status that will be sent to the e-commerce system for '
            'orders marked as shipped in Odoo.'
        ),
    )

    run_action_on_so_invoice_status = fields.Boolean(
        string='Sync Invoiced/Paid SO Status',
        copy=False,
        help=(
            'Enable this option to update the order status in the e-commerce system for '
            'sales orders that are invoiced or marked as paid in Odoo. Specific behaviors '
            'based on the payment method can be configured under '
            '"Auto-Workflow → Payment Methods", where you can adjust when the payment status '
            'is sent. By default, the action occurs when an order is fully invoiced, '
            'and all related invoices are "Paid" or "In Payment".'
        ),
    )

    sub_status_paid_id = fields.Many2one(
        comodel_name='sale.order.sub.status',
        string='Store Order Status for Invoiced/Paid SO',
        domain='[("integration_id", "=", id)]',
        copy=False,
        help=(
            'Choose the store order status to be applied to orders in the e-commerce system once '
            'the corresponding sales order in Odoo is fully paid.'
        ),
    )

    apply_to_products = fields.Boolean(
        string='Auto-Export New Products',
        default=False,
        help=(
            'Enable automatic export of newly created Odoo products to the e-commerce system, '
            'ensuring all new inventory items are synchronized.'
        ),
    )

    auto_create_products_on_so = fields.Boolean(
        string='Auto-Create Missing Products',
        default=False,
        help=(
            'Automatically create a new product in Odoo if a product from an imported '
            'sales order does not match any existing product mappings. If disabled, '
            'sales order import will fail, and manual products mapping will be required '
            'by an administrator.'
        )
    )

    auto_create_taxes_on_so = fields.Boolean(
        string='Auto-Create Missing Taxes',
        default=False,
        help=(
            'Enable the automatic creation of tax entries in Odoo when a sales order '
            'is imported with taxes that do not have predefined mappings. Without this '
            'setting enabled, the import of the sales order will fail, and manual tax '
            'mapping will be required by an administrator.'
        )
    )

    auto_create_delivery_carrier_on_so = fields.Boolean(
        string='Auto-Create Missing Delivery Carriers',
        default=False,
        help=(
            'Automatically generate a new delivery carrier entry in Odoo if the carrier '
            'specified in an imported sales order does not exist. If this option is not enabled, '
            'the absence of a delivery carrier will cause the sales order import to fail, '
            'and manual delivery carrier mapping will be required by an administrator.'
        ),
    )

    apply_external_fulfillments = fields.Boolean(
        string='Auto-Apply Fulfillments from E-Commerce System',
        default=False,
        help=(
            'Automatically apply fulfillments from the e-commerce system to matching'
            'sales orders in Odoo. This happens after orders are automatically confirmed in Odoo '
            '(if auto-workflow is enabled with "Confirm Order" action).'
        ),
    )

    apply_external_payments = fields.Boolean(
        string='Auto-Apply Payments from E-Commerce System',
        default=False,
        help=(
            'Automatically Apply Payments from E-Commerce System to Matching Sales Orders in Odoo. '
            'Payments from the E-Commerce System are now automatically applied to corresponding sales orders in Odoo. '
            'This process occurs after order invoices are automatically confirmed in Odoo '
            '(if the auto-workflow is enabled with the "Confirm Invoice" action).'
        ),
    )

    integration_writeoff_account_id = fields.Many2one(
        comodel_name='account.account',
        string='Default Write-off Account',
        default=False,
        help=(
            'The write-off account is used to record the difference between the payment '
            'downloaded from E-Commerce System and the invoice total in Odoo.'
        ),
    )

    force_full_fulfillment = fields.Boolean(
        string='Force Shopify Order Fulfillment (Debug)',
        default=False,
        help=(
            'Use only if experiencing fulfillment issues. Forces complete fulfillment of Shopify orders, '
            'even if there are discrepancies between the Odoo shipment and the original order '
            '(e.g., different quantities or missing items). This can be helpful in troubleshooting scenarios '
            'where automatic fulfillment fails.'
        ),
    )

    webhook_line_ids = fields.One2many(
        comodel_name='integration.webhook.line',
        inverse_name='integration_id',
        string='Webhook Lines',
        help="""WEBHOOK STATES:

            - Green: active webhook.
            - Red: inactive webhook.
            - Yellow: webhook need to be recreated, click button "Create Webhooks" above.
        """,
    )

    save_webhook_log = fields.Boolean(
        string='Enable Webhook Event Logging',
        help=(
            'Turn this on to log all webhook events related to order status changes in the '
            'e-commerce system. This can aid in monitoring and troubleshooting '
            'the order status update process.'
        ),
    )

    allow_import_images = fields.Boolean(
        string='Enable Images Import',
        default=True,
        help='Allow import images during product import from the e-commerce system.',
    )

    allow_export_images = fields.Boolean(
        string='Enable Images Export',
        default=True,
        help=(
            'Enable this feature to automatically update and export product images from Odoo '
            'to your e-commerce platform during products synchronization.'
        ),
    )

    synchronise_qty_field = fields.Selection(
        selection='_calc_qty_fields_selections',
        string='Inventory Quantity Source Field',
        required=True,
        default='free_qty',
        help=(
            'Select the field in Odoo which should be used to update the stock levels on the '
            'e-commerce platform. This is typically the "Quantity on Hand" or a custom field '
            'representing available stock.'
        ),
    )

    send_inactive_product = fields.Boolean(
        string='Mark as Inactive on First Export',
        help=(
            'Enable this to export new products as "inactive" to the external system, '
            'allowing for additional reviews and edits before they are published.'
        ),
    )

    request_order_url = fields.Char(
        string='Invoice Request Endpoint',
        compute='_compute_request_order_url',
        help=(
            'This is the fixed URL endpoint you should use in the e-commerce system '
            'to request invoices by order ID.'
        ),
    )

    mandatory_fields_initial_product_export = fields.Many2many(
        string='Required Fields for Initial Export',
        comodel_name='ir.model.fields',
        required=True,
        help=(
            'Determine the fields that must be populated in Odoo for a product '
            'to qualify for export to the external system.'
        ),
        domain='[("model", "=", "product.product")]',
        default=lambda self: self._get_default_mandatory_fields(),
    )

    select_send_sale_price = fields.Selection(
        string='Conversion method for Sales Price',
        selection=[
            ('no_changes', 'No changes'),
            ('tax_included', 'Send tax included Sales Price (B2C)'),
            ('tax_excluded', 'Send tax excluded Sales Price (B2B)'),
        ],
        default='no_changes',
        required=True,
        help=(
            'Specify the conversion method for the "Sales Price" during export, as set in the '
            '"Product field mapping". The conversion takes into account the tax settings '
            'from the Product template in Odoo.'
        ),
    )

    behavior_on_empty_tax = fields.Selection(
        selection=[
            ('leave_empty', 'Leave Empty'),
            ('set_special_tax', 'Set Special Tax'),
            ('take_from_product', ' Take from the Product'),
        ],
        string='Behavior on Empty Taxes',
        default='leave_empty',
        required=True,
        help=(
            'Define the action to be taken for sales order lines that do not have associated '
            'tax data. This helps maintain accurate tax reporting and compliance.'
        ),
    )

    zero_tax_id = fields.Many2one(
        comodel_name='account.tax',
        string='Special Zero Tax',
    )

    pricelist_integration = fields.Boolean(
        string='Pricelists Synchronization',
        help=(
            'Toggle this option to enable the synchronization of pricelists and their items '
            'between e-commerce system and Odoo. When active, updates to pricelists in either '
            'system can be imported and reflected in the other.'
        ),
    )

    invoice_report_id = fields.Many2one(
        comodel_name='ir.actions.report',
        string='Invoice Report Template',
        domain=[
            ('model', '=', 'account.move'),
        ],
        help=(
            'Select the invoice report template that will be utilized to generate '
            'the PDF file for invoices.'
        ),
        default=lambda self: self.env.ref('account.account_invoices').id,
    )

    behavior_on_non_existing_invoice = fields.Selection(
        selection=[
            ('return_not_exist', 'Return Message That Invoice Does Not Exist'),
            ('try_generate', 'Try to Generate and Confirm Invoice'),
        ],
        string='No-Invoice Response Action',
        default='return_not_exist',
        required=True,
        help=(
            'Determine the system\'s response when an invoice is not found for a sales order. '
            'Select "Return Message That Invoice Does Not Exist" to notify that the invoice doesn\'t exist, or choose '
            '"Try to Generate and Confirm Invoice" to automatically create and finalize the invoice.'
        ),
    )

    orders_cut_off_datetime = fields.Datetime(
        string='Orders Cut-off date',
        default=fields.Datetime.now,
        help=(
            'Sets a cut-off date for order imports, based on the date of creation from the '
            'E-Commerce system. Orders created before the "Orders Cut-off Date" will not be '
            'imported, regardless of any updates or changes made after this date.'
        ),
    )

    orders_cut_off_datetime_str = fields.Char(
        string='Orders Cut-off Date String',
        compute='_compute_orders_cut_off_datetime_str',
    )

    check_weight_uoms = fields.Boolean(
        compute='_compute_check_weight_uoms',
        string='Check Weight Uoms',
    )

    price_including_taxes = fields.Boolean(
        string='Price Including Tax',
        help=(
            'Toggle this to align tax inclusion settings between Odoo and e-commerce system, '
            'ensuring taxes are correctly marked as "Included in Price" within Odoo.'
        ),
    )

    global_tracked_fields = fields.Many2many(
        string='Product Sync Watch Fields',
        comodel_name='ir.model.fields',
        relation='sale_integration_global_tracked_fields_rel',
        help=(
            'Choose the Odoo product fields that, when altered, will trigger an automatic '
            'export of the product details to the connected e-commerce platform.'
        ),
        domain='[("model", "in", ["product.template", "product.product"])]',
        default=lambda self: self._get_default_global_tracked_fields(),
    )

    validate_barcode = fields.Boolean(
        string='Variant Barcode Validation',
        help=(
            'Enable this option to check for missing barcodes for product variants. '
            'This setting only works when the "Receive field on import" option '
            'is enabled for the barcode field for this integration under '
            'Integration → Product Fields → Product Field Mapping.'
        ),
    )

    is_import_dynamic_attribute = fields.Boolean(
        string='Dynamic Attribute Import Mode',
        help=(
            'Enable this to allow the e-commerce connector to import product '
            'attributes dynamically, creating only the necessary variants in Odoo '
            'based on the available combinations in the external system, '
            'and avoiding the generation of non-existent variants.'
        ),
    )

    integration_pricelist_id = fields.Many2one(
        string='Regular Pricelist for Product Export',
        comodel_name='product.pricelist',
        help=(
            'Choose the pricelist that will be used to determine product prices during the '
            'export process. This is the default pricelist for general product exports.\n\n'
            'Note: The pricelist must be able to calculate final product prices without quantity '
            'information (using quantity = 0). Dynamic values are supported, but complex formulas '
            'with minimum quantity requirements are not supported.'
        ),
    )

    integration_sale_pricelist_id = fields.Many2one(
        string='Sale Pricelist for Product Export',
        comodel_name='product.pricelist',
        help=(
            'Select the pricelist that will be used to trigger automatic product updates in your e-commerce '
            'system when price changes occur. This pricelist is specifically used for sales-related price updates '
            'and will automatically sync price changes to the external system.\n\n'
            'Note: The pricelist must be able to calculate final product prices without quantity '
            'information (using quantity = 0). Dynamic values are supported, but complex formulas '
            'with minimum quantity requirements are not supported.'
        ),
    )

    # The fields below used to show statistics card on kanban view
    orders_count = fields.Integer(
        string='Total Orders',
        compute='_compute_orders_count',
        store=False,
    )

    orders_today_count = fields.Integer(
        string='Today Orders',
        compute='_compute_orders_today_count',
        store=False,
    )

    queued_or_failed_orders_count = fields.Integer(
        string='Total Failed Orders',
        compute='_compute_queued_or_failed_orders_count',
        store=False,
    )

    orders_last_7_days_chart_data = fields.Json(
        string='Orders Last 7 Days Chart Data',
        compute='_compute_orders_last_7_days_chart_data',
        store=False,
    )
    orders_last_7_days_chart_data_cache = fields.Json(
        string='Orders Chart Cache',
    )

    failed_jobs_count = fields.Integer(
        string='Failed Jobs Count',
        compute='_compute_failed_jobs_count',
        store=False,
    )
    products_count = fields.Integer(
        string='Products Count',
        compute='_compute_products_count',
        store=False,
    )

    product_bundle_policy = fields.Selection(
        selection=[
            ('create_bundle', 'Create as Bundle'),
            ('decompose_bundle', 'Decompose into Components'),
        ],
        string='Bundle Handling Policy',
        default='create_bundle',
        required=True,
        help=(
            'Choose how the connector should handle bundle or composite products included in '
            'incoming orders. Select "Create as Bundle" to treat the bundle as a single kit '
            'product in Odoo. Choose "Decompose into Components" if you prefer to break down '
            'the bundle into its individual component products for the order.'
        ),
    )

    separate_discount_line = fields.Boolean(
        string='Add Discounts as a Separate Order Lines',
        default=True,
        help=(
            'This setting controls how discounts are applied to orders. When enabled, each '
            'discount is added as a separate line item for every product that requires a discount. '
            'If disabled, the connector calculates the discount percentage and applies it directly '
            'to the corresponding product\'s order line by utilizing the Discount field.'
        ),
    )

    change_advanced_fields = fields.Boolean(
        string='Change Advanced Product Fields',
    )

    template_reference_id = fields.Many2one(
        comodel_name='product.ecommerce.field',
        string='Template Reference',
        ondelete='restrict',
    )

    product_reference_id = fields.Many2one(
        comodel_name='product.ecommerce.field',
        string='Variant Reference',
        ondelete='restrict',
    )

    template_barcode_id = fields.Many2one(
        comodel_name='product.ecommerce.field',
        string='Template Barcode',
        ondelete='restrict',
    )

    product_barcode_id = fields.Many2one(
        comodel_name='product.ecommerce.field',
        string='Variant Barcode',
        ondelete='restrict',
    )

    fallback_product_id = fields.Many2one(
        comodel_name='product.product',
        string='Fallback Product',
        domain="[('type', '=', 'service')]",
        help=(
            'Use this field to select a default product for order lines with missing '
            'SKU and ID details. It\'s applicable when products are removed or '
            'orders contain custom items, ensuring uninterrupted order processing.'
        ),
    )

    use_manual_customer_mapping = fields.Boolean(
        string='Enable Manual Customer Mapping',
        help=(
            'Enable this option to switch to manual mapping of customers in the '
            'Mappings → Contacts section. This setting is suitable for B2B with a small '
            'customer base, where each customer\'s details require verification before being '
            'added to Odoo.'
        ),
    )

    emails_for_failed_mapping_notifications = fields.Char(
        string='Emails to Notify about Failed Customer Mapping',
        help=(
            'Enter a list of email addresses (separated by commas) to receive notifications in '
            'case of unsuccessful customer mapping. This feature will work only when manual '
            'customer mapping is enabled.'
        ),
    )

    skip_individual_contacts = fields.Boolean(
        string='Use Company as Contact When Available (Experimental)',
        help=(
            'When enabled, the connector will use the company as the contact instead of creating '
            'individual contact records when company information is available. This is particularly '
            'useful for B2B scenarios where you want to maintain a cleaner contact structure by '
            'avoiding duplicate individual contacts for the same company.'
        ),
    )

    use_vat_only_company_search = fields.Boolean(
        string='Search Companies by VAT Number Only',
        help=(
            'Enable to search companies by VAT number only. Ensure the "VAT / Reg. Number" field '
            'is filled for use.'
        ),
    )

    use_order_total_difference_correction = fields.Boolean(
        string='Order Total Difference Correction',
        default=True,
        help=(
            'Enable this option to automatically correct the difference in total order amount '
            'when importing orders from E-Commerce Systems.'
        ),
    )

    search_customer_fields_ids = fields.Many2many(
        string='Search Customer Fields',
        comodel_name='ir.model.fields',
        relation='integration_search_customer_fields_rel',
        column1='integration_id',
        column2='field_id',
        domain=lambda self: [
            ('model', '=', 'res.partner'), ('name', 'in', SEARCH_CUSTOMER_FIELDS),
        ],
        default=lambda self: self._default_search_customer_fields_ids(),
        help=(
            'List of res.partner fields to use when searching for existing customers '
            'in Odoo (e.g. during order import). '
            'Default fallback: Name, Email, Phone, and Mobile if all selected fields are empty.'
        ),
    )

    use_search_customer_fields_ids = fields.Boolean(
        string='Use Selected Customer Fields for Search',
        help=(
            'Indicates that a specific set of partner search fields is used. Technical field.'
        ),
    )

    ignore_vat_validation = fields.Boolean(
        string='Ignore VAT validation',
        help=(
            'If that is checked, connector will skip checking company tax identification number '
            'for validity and will insert it as is on the partner.'
        ),
    )
    use_odoo_so_numbering = fields.Boolean(
        string='Use Odoo SO numbering',
        help='Enable this option to use Odoo sales order numbering instead of the e-commerce system\'s numbering.',
    )

    update_fiscal_position = fields.Boolean(
        string='Automatically update taxes based on Fiscal Position',
    )

    default_tax_scope = fields.Selection(
        selection=[
            ('service', 'Services'),
            ('consu', 'Goods'),
        ],
        string='Tax Scope',
        help='Select a default tax scope to automatically create taxes.'
    )

    default_tax_group_id = fields.Many2one(
        string='Tax Group',
        comodel_name='account.tax.group',
        help='Select a default tax group to automatically create taxes.',
    )

    default_account_id = fields.Many2one(
        string='Account',
        comodel_name='account.account',
        check_company=True,
        help='Select a default account to automatically create taxes.',
    )

    update_stock_for_manufacture_boms = fields.Boolean(
        string='Calculate Stock for "Manufacture" BoMs',
        help=(
            'Enable this option to allow the connector to calculate stock levels for products '
            'with a "Manufacture" BoM based on the stock levels of its sub-components. The computed '
            'stock will be synchronized with the e-commerce store.'
        ),
    )

    ignore_boms_for_product_export = fields.Boolean(
        string='Ignore BoMs for Product Export',
        help=(
            'Enable this option to export products as standalone items, ignoring any attached BoMs.'
            'When enabled, products will be exported as simple products (not kits or bundles),'
            'and BoM-related details will not be included in the e-commerce system.'
        ),
    )

    is_integration_shopify = fields.Boolean(
        string='Is Shopify',
        compute='_compute_integration_type',
    )

    is_integration_prestashop = fields.Boolean(
        string='Is PrestaShop',
        compute='_compute_integration_type',
    )

    is_integration_magento_two = fields.Boolean(
        string='Is Magento 2',
        compute='_compute_integration_type',
    )

    is_integration_woocommerce = fields.Boolean(
        string='Is WooCommerce',
        compute='_compute_integration_type',
    )

    order_name_ref = fields.Char(
        string='Sales Order Prefix',
        help=(
            'Set a unique prefix for orders to easily identify those imported from this '
            'integration. This prefix will precede the order number in Odoo.'
        ),
    )

    so_external_reference_field = fields.Many2one(
        string='Sales Order External Reference Field',
        comodel_name='ir.model.fields',
        ondelete='cascade',
        help=(
            'Specify a Sales Order field (character or text types only) to record an external '
            'sales order number. This is supplementary to the "E-Commerce Order Reference" field '
            'and can be used for enhanced order tracking and integration purposes.'
        ),
        required=False,
        domain='[("store", "=", True), '
               '("model_id.model", "=", "sale.order"), '
               '("ttype", "in", ("text", "char")) ]',
    )

    so_delivery_note_field = fields.Many2one(
        string='Sales Order Delivery Note Field',
        comodel_name='ir.model.fields',
        ondelete='cascade',
        help=(
            'Specify the Sales Order field (character or text types only) where the Delivery Note '
            'from the e-commerce system will be recorded. By default, the system uses the field '
            'specified under the e-commerce tab of the Sales Order. However, you can designate '
            'any compatible field, including those from third-party modules.'
        ),
        required=True,
        default=lambda self: self.env.ref('integration.field_sale_order__integration_delivery_note').id,
        domain='[("store", "=", True), '
               '("model_id.model", "=", "sale.order"), '
               '("ttype", "in", ("text", "char")) ]',
    )

    picking_delivery_note_field = fields.Many2one(
        string='Stock Picking Delivery Note Field',
        comodel_name='ir.model.fields',
        ondelete='cascade',
        help=(
            'Specify the Stock Picking field (character or text types only) to capture the '
            'Delivery Note from the e-commerce system. The "Note" field on Stock Picking is used '
            'as the standard field, but you have the flexibility to assign any compatible field, '
            'including those from third-party modules.'
        ),
        required=True,
        default=lambda self: self.env.ref('stock.field_stock_picking__note').id,
        domain='[("store", "=", True), '
               '("model_id.model", "=", "stock.picking"), '
               '("ttype", "in", ("text", "char")) ]',
    )

    default_sales_team_id = fields.Many2one(
        string='Default Sales Team for Orders',
        comodel_name='crm.team',
        help=(
            'Select a default Sales Team to be automatically assigned to all Sales Orders '
            'imported from the e-commerce system.'
        ),
        check_company=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]"
    )

    keep_sales_person_empty = fields.Boolean(
        string='Keep Sales Person Empty',
        default=False,
        help=(
            'If enabled, the Sales Person field will be left empty for imported orders, '
            'similar to how eCommerce (website_sale) module works. When enabled, the "Default Sales Person for Orders" '
            'field below will be ignored and cleared.'
        ),
    )

    default_sales_person_id = fields.Many2one(
        string='Default Sales Person for Orders',
        comodel_name='res.users',
        help=(
            'Select a default Sales Person to be automatically assigned to all Sales Orders imported '
            'from the e-commerce system. This field will be ignored if the "Keep Sales Person Empty" '
            'field is enabled.',
        ),
        check_company=True,
        domain="['|', ('id', '=', 1), '&', ('active', '=', True), '|', ('company_id', '=', False), ('company_id', '=', company_id)]"  # NOQA
    )

    customer_company_vat_field = fields.Many2one(
        string='VAT/Reg. Number Field',
        comodel_name='ir.model.fields',
        ondelete='cascade',
        help=(
            'Identify the field in the Company record (limited to character type fields) to store '
            'the Company\'s VAT/Registration Number from the e-commerce system. While the default '
            'is the VAT field on the Company, you can designate any custom field, '
            'including those from third-party modules.'
        ),
        required=False,
        domain='[("store", "=", True), '
               '("model_id.model", "=", "res.partner"), '
               '("ttype", "=", "char") ]',
    )

    customer_company_vat_field_name = fields.Char(
        related='customer_company_vat_field.name',
    )

    customer_personal_id_field = fields.Many2one(
        string='Personal ID Field',
        comodel_name='ir.model.fields',
        ondelete='cascade',
        help=(
            'Specify the field in the Contact record (limited to character type fields) where the '
            'Personal ID Number from the e-commerce system will be stored. This is particularly '
            'important for localizations that require personal identification, '
            'such as the Italian market.'
        ),
        required=False,
        domain='[("store", "=", True), '
               '("model_id.model", "=", "res.partner"), '
               '("ttype", "=", "char") ]',
    )

    default_customer = fields.Many2one(
        string='Default Customer',
        comodel_name='res.partner',
        help=(
            'Specify a default customer in Odoo for orders that lack customer information in the '
            'E-Commerce System. This ensures all orders are associated with a customer record.'
        ),
    )

    external_order_field_mapping_ids = fields.One2many(
        comodel_name='external.order.field.mapping',
        inverse_name='integration_id',
        context={'active_test': False},
        string='External Order Field Mappings',
        help=(
            'Define the mapping between fields in the e-commerce system and Odoo. '
        )
    )

    allow_multi_company_inventory_calculation = fields.Boolean(
        string='Allow Multi-Company Inventory Calculation',
        help='When enabled, producible quantity will be calculated across all companies '
             'for locations mapped to the same external location. ',
    )

    export_prices_cron_id = fields.Many2one(
        comodel_name='ir.cron',
        string='Export Prices Cron',
    )

    export_prices_cron_id_lastcall = fields.Datetime(
        string='Export Prices Last Run',
        related='export_prices_cron_id.lastcall',
        help='The last time the Export Prices cron job was executed.',
    )

    export_prices_cron_id_nextcall = fields.Datetime(
        string='Export Prices Next Planned Run',
        related='export_prices_cron_id.nextcall',
        help='The next scheduled execution time for the Export Prices cron job.',
    )

    export_prices_cron_id_active = fields.Boolean(
        string='Enable Prices Calculation and Export',
        related='export_prices_cron_id.active',
        readonly=False,
        help=(
            'If enabled, Odoo will calculate prices based on pricelists, '
            'and business rules, then export them to E-Commerce System.'
        ),
    )

    api_access_granted = fields.Boolean(
        string='API Access Granted',
        compute='_compute_api_access_granted',
    )

    apply_company_on_product = fields.Boolean(
        string='Apply Company on Product',
        help=(
            'Enable this option to automatically set the company_id for products during their creation. '
            'This ensures that the products are associated with the same company as the integration.'
        ),
    )

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f'[{rec.type_api}] {rec.name}'

    @api.depends('field_ids')
    def _compute_api_access_granted(self):
        for rec in self:
            rec.api_access_granted = rec.get_settings_value('access_granted', False)

    def _compute_integration_type(self):
        for rec in self:
            rec.is_integration_shopify = rec.type_api == 'shopify'
            rec.is_integration_prestashop = rec.type_api == 'prestashop'
            rec.is_integration_magento_two = rec.type_api == 'magento2'
            rec.is_integration_woocommerce = rec.type_api == 'woocommerce'

    @property
    def is_no_api(self):
        self.ensure_one()
        return self.type_api == 'no_api'

    def is_translations_needed(self, *args, **kw):
        # magento2: True
        # prestashop: True
        # shopify, woocommerce --> is calculated
        self.ensure_one()
        return True

    def _default_search_customer_fields_ids(self):
        return self.env['ir.model.fields'].sudo().search([
            ('model', '=', 'res.partner'),
            ('name', 'in', SEARCH_CUSTOMER_FIELDS),
        ])

    def _set_default_template_reference_id(self):
        """Redefine it"""
        if not self.is_no_api:
            return False

        self.template_reference_id = self.env.ref(
            'integration.integration_template_reference_no_api_private').id
        return bool(self.template_reference_id)

    def _set_default_product_reference_id(self):
        """Redefine it"""
        if not self.is_no_api:
            return False

        self.product_reference_id = self.env.ref(
            'integration.integration_product_reference_no_api_private').id
        return bool(self.product_reference_id)

    def _set_default_template_barcode_id(self):
        """Redefine it"""
        if not self.is_no_api:
            return False

        self.template_barcode_id = self.env.ref(
            'integration.integration_template_barcode_no_api_private').id
        return bool(self.template_barcode_id)

    def _set_default_product_barcode_id(self):
        """Redefine it"""
        if not self.is_no_api:
            return False

        self.product_barcode_id = self.env.ref(
            'integration.integration_product_barcode_no_api_private').id
        return bool(self.product_barcode_id)

    @api.onchange('search_customer_fields_ids')
    def _onchange_search_customer_fields_ids(self):
        self.use_search_customer_fields_ids \
            = len(self.search_customer_fields_ids) < len(SEARCH_CUSTOMER_FIELDS)

    @api.constrains('search_customer_fields_ids')
    def _check_search_customer_fields_ids(self):
        if not self.search_customer_fields_ids:
            raise ValidationError(_(
                'At least one search customer field must remain.\n\n'
                'You cannot remove all search customer fields from the configuration.'
            ))

    @api.onchange('customer_company_vat_field')
    def _onchange_customer_company_vat_field(self):
        """
        Update the 'use_search_company_by_vat' field based on the 'customer_company_vat_field'.

        If the VAT field is not specified, automatically disable the option to search for
        companies by VAT.
        """
        if not self.customer_company_vat_field:
            self.use_vat_only_company_search = False

    @api.onchange('keep_sales_person_empty')
    def _onchange_keep_sales_person_empty(self):
        """
        Clear the default_sales_person_id field when keep_sales_person_empty is enabled.
        """
        if self.keep_sales_person_empty:
            self.default_sales_person_id = False

    @api.onchange('emails_for_failed_mapping_notifications')
    def _onchange_emails_for_failed_mapping_notifications(self):
        """
        Onchange method triggered when notify_on_failed_mapping field changes.
        It validates the email addresses and displays a warning for invalid ones.
        """
        if self.emails_for_failed_mapping_notifications:
            email_addresses = [
                email.strip() for email in self.emails_for_failed_mapping_notifications.split(',')
            ]

            invalid_emails = [
                email for email in email_addresses if email and not _is_valid_email(email)
            ]

            if invalid_emails:
                return {
                    'warning': {
                        'title': 'Invalid Email Addresses',
                        'message': f"Invalid email addresses: {', '.join(invalid_emails)}"
                    }
                }

    def _get_default_global_tracked_fields(self):
        return self.env['ir.model.fields'].sudo().search([
            ('model', 'in', ['product.template', 'product.product']),
            ('name', 'in', TRACKED_FIELDS_INITIAL_PRODUCT_EXPORT),
        ])

    @api.onchange('orders_cut_off_datetime')
    def _onchange_orders_cut_off_date(self):
        if self.orders_cut_off_datetime:
            self.last_receive_orders_datetime = self.orders_cut_off_datetime

    def _get_default_mandatory_fields(self):
        return self.env['ir.model.fields'].sudo().search([
            ('model', '=', 'product.product'),
            ('name', '=', 'default_code'),
        ])

    def _compute_lang_ids(self):
        Mapping = self.env['integration.res.lang.mapping']

        for rec in self:
            records = Mapping.search([
                ('language_id', '!=', False),
                ('integration_id', '=', rec.id),
            ]).mapped('language_id')

            rec.lang_ids = records.filtered('active')

    def _compute_request_order_url(self):
        host = self.get_base_url_config()
        db_name = self.env.cr.dbname
        integration_api_key = self.get_integration_api_key() or ''

        pattern = f'{host}/{db_name}/integration/integration_id/external-order/' \
                  f'%order_id%?integration_api_key={integration_api_key}'
        for integration in self:
            url = pattern.replace('integration_id', str(integration.id))
            integration.request_order_url = url

    def _compute_next_inventory_synchronization_date(self):
        for integration in self.filtered('inventory_synchronization_cron_id'):
            cron = integration.inventory_synchronization_cron_id.sudo()
            integration.next_inventory_synchronization_date = cron.nextcall

    def _inverse_next_inventory_synchronization_date(self):
        for integration in self.filtered('inventory_synchronization_cron_id'):
            cron = integration.inventory_synchronization_cron_id.sudo()
            cron.nextcall = integration.next_inventory_synchronization_date

    def _get_weight_integration_fields(self):
        """
        This method returns list of product.ecommerce.field for import/export weight
        It should be overloaded in connector modules
        """
        return []

    def _compute_check_weight_uoms(self):
        odoo_weight_uom = self.env['product.template']._get_weight_uom_id_from_ir_config_parameter()
        odoo_weight_uom_name = normalize_uom_name(odoo_weight_uom.name)

        for integration in self:
            if integration.state != 'active':
                integration.check_weight_uoms = True
                continue

            # Check that import and export product weight are switched on
            fields_name = integration._get_weight_integration_fields()
            fields_ids = [self.env.ref(x).id for x in fields_name]

            fields_mapping = self.env['product.ecommerce.field.mapping'].search([
                ('integration_id', '=', integration.id),
                ('ecommerce_field_id', 'in', fields_ids),
                ('import_enabled', '=', True),
                ('export_enabled', '=', True),
            ])
            if not fields_mapping:
                integration.check_weight_uoms = True
                continue
            try:
                adapter = self.adapter
                ext_weight_uom = adapter.get_weight_uoms()
            except Exception:
                integration.check_weight_uoms = True
                continue

            ext_weight_uom = [normalize_uom_name(x) for x in ext_weight_uom]
            result = all([odoo_weight_uom_name == x for x in ext_weight_uom])
            integration.check_weight_uoms = result

    @api.depends('last_receive_orders_datetime')
    def _compute_last_receive_orders_datetime_str(self):
        for integration in self:
            if integration.last_receive_orders_datetime:
                value = integration.last_receive_orders_datetime.strftime(
                    DATETIME_FORMAT,
                )
            else:
                value = ''

            integration.last_receive_orders_datetime_str = value

    @api.depends('orders_cut_off_datetime')
    def _compute_orders_cut_off_datetime_str(self):
        for integration in self:
            if integration.orders_cut_off_datetime:
                value = integration.orders_cut_off_datetime.strftime(
                    DATETIME_FORMAT,
                )
            else:
                value = ''

            integration.orders_cut_off_datetime_str = value

    def _compute_orders_count(self):
        """
        Compute number of external files (orders)
        """
        for integration in self:
            integration.orders_count = self.env['sale.integration.input.file'].search_count([
                ('si_id', '=', integration.id),
            ])

    def _compute_orders_today_count(self):
        """
        Compute number of external files (orders) created today
        """
        for integration in self:
            integration.orders_today_count = self.env['sale.integration.input.file'].search_count([
                ('si_id', '=', integration.id),
                ('create_date', '>=', fields.Datetime.now() - timedelta(days=1)),
            ])

    def _compute_queued_or_failed_orders_count(self):
        """
        Compute number of queued or failed orders based on empty Sales Order ID
        """
        for integration in self:
            integration.queued_or_failed_orders_count = self.env['sale.integration.input.file'].search_count([  # NOQA
                ('si_id', '=', integration.id),
                ('order_id', '=', False),
            ])

    def _compute_orders_last_7_days_chart_data(self):
        """Compute order counts for the last 7 days. Uses cache (1 hour TTL)."""
        for integration in self:
            cache = integration.orders_last_7_days_chart_data_cache or {}

            # Use cache if valid
            if cache.get('cached_at') and time() - cache['cached_at'] < 3600:  # TODO: Move to constant?
                integration.orders_last_7_days_chart_data = cache
                continue

            # Recompute
            data = integration._get_orders_last_7_days_data()
            data['cached_at'] = time()

            # Update cache and field
            integration.orders_last_7_days_chart_data_cache = data
            integration.orders_last_7_days_chart_data = data

    def _get_orders_last_7_days_data(self):
        """Fetch order counts for the last 7 days from database."""
        self.ensure_one()
        InputFile = self.env['sale.integration.input.file']
        today = fields.Date.today()
        labels, values = [], []

        for i in range(6, -1, -1):
            day = today - timedelta(days=i)
            count = InputFile.search_count([
                ('si_id', '=', self.id),
                ('create_date', '>=', datetime.combine(day, datetime.min.time())),
                ('create_date', '<=', datetime.combine(day, datetime.max.time())),
            ])
            labels.append(day.strftime('%a'))
            values.append(count)

        return {'labels': labels, 'values': values}

    def _compute_failed_jobs_count(self):
        """Compute number of failed jobs for this integration."""
        for integration in self:
            integration.failed_jobs_count = integration._get_integration_failed_jobs_count()

    def _compute_products_count(self):
        """Compute number of product mappings for this integration."""
        ProductMapping = self.env['integration.product.template.mapping']
        for integration in self:
            integration.products_count = ProductMapping.search_count([
                ('integration_id', '=', integration.id),
            ])

    def action_view_products(self):
        """Open product mappings for this integration."""
        self.ensure_one()
        return {
            'name': _('Products'),
            'type': 'ir.actions.act_window',
            'res_model': 'integration.product.template.mapping',
            'view_mode': 'list,form',
            'domain': [('integration_id', '=', self.id)],
            'context': {'default_integration_id': self.id},
        }

    def action_view_failed_jobs(self):
        """Open failed jobs for this integration using custom views."""
        self.ensure_one()
        return self.get_failed_jobs_action(self.id)

    @api.model
    def _calc_qty_fields_selections(self):
        return [
            (field_name, self.env['product.product']._get_field_string(field_name))
            for field_name in PRODUCT_QTY_FIELDS
        ]

    def get_integration_api_key(self):
        """ Get API key for the installed integration. """
        return self.env['ir.config_parameter'].sudo().get_param('integration.integration_api_key')

    def generate_integration_api_key(self):
        """ Generate API key for the installed integration. """
        api_key = binascii.hexlify(os.urandom(API_KEY_SIZE)).decode()
        self.env['ir.config_parameter'].sudo().set_param('integration.integration_api_key', api_key)

        return self.get_integration_api_key()

    def is_carrier_tracking_required(self):
        """
        Value for filtering `done order pickings`
        during `order_export_tracking()` method performing.
        """
        return False

    def format_integration_version_info(self):
        """
        Get formatted version information for all integration modules.
        """
        # Get all integration-related modules
        all_modules = self.env['ir.module.module'].search([
            ('name', 'in', INTEGRATION_MODULES)
        ])

        version_info = []

        # Check each module from the list
        for module in all_modules:
            status = "✓ INSTALLED" if module.state == 'installed' else "✗ NOT INSTALLED"
            version = module.latest_version or module.installed_version or 'Unknown'
            version_info.append(f"{module.name:<25} | {version:<12} | {status:<15}")

        return '\n'.join(version_info)

    def get_fallback_product_or_raise(self, complex_product_id: str, product_name: str, product_reference: str):
        self.ensure_one()

        if self.fallback_product_id:
            return self.fallback_product_id

        template_code, variant_code = self.adapter._parse_product_external_code(complex_product_id)

        raise ValidationError(
            _(
                'The order contains a line item with missing product details (either product ID or SKU is empty).\n\n'
                'Missing Product Information:\n'
                '- Product Template ID: %(template_code)s\n'
                '- Product Variant ID: %(variant_code)s\n'
                '- Product Name: %(product_name)s\n'
                '- Product Reference: %(product_reference)s\n\n'
                'This typically happens when products are removed from the external system or custom '
                'items are added via order editing. '
                'Product information is required to import the order into Odoo.\n\n'
                'To resolve this issue, you can do one of the following:\n'
                '1. Configure a Fallback Product in E-Commerce Integrations → Stores → '
                '<your store> → Sales Orders tab.\n'
                '2. Manually adjust the order in the external system to correct '
                'the missing product information.\n'
                '3. Check if the product with Template ID=%(template_code)s and Variant-ID=%(variant_code)s '
                'still exists in the external e-commerce system.\n\n'
                'Once this is done, requeue the job to continue processing the order.'
            ) % {
                'template_code': template_code,
                'variant_code': variant_code,
                'product_name': product_name,
                'product_reference': product_reference,
            }
        )

    def open_webhooks_logs(self):

        integration_log = self.env['integration.logging'].search([
            ('integration_id', '=', self.id),
            ('event_type', '=', 'webhook'),
        ])

        return {
            'type': 'ir.actions.act_window',
            'name': 'Integration Webhook Logs',
            'res_model': integration_log._name,
            'view_mode': 'list,form',
            'domain': [('id', 'in', integration_log.ids)],
            'target': 'current',
        }

    def _get_error_webhook_message(self, error):
        return _('Not Implemented!')

    def create_webhooks(self, raise_original=False):
        self.ensure_one()
        routes_dict = self.prepare_webhook_routes()
        external_ids = self.webhook_line_ids.mapped('external_ref')
        adapter = self.adapter

        try:
            adapter.unlink_existing_webhooks(external_ids)
            data_dict = adapter.create_webhooks_from_routes(routes_dict)
        except Exception as ex:
            if raise_original:
                raise ex

            message = self._get_error_webhook_message(ex) if ex.args else ex
            return self.env['message.wizard'].create_html_and_run(message)

        return self.create_integration_webhook_lines(data_dict)

    def drop_webhooks(self):
        result = False
        external_ids = self.webhook_line_ids.mapped('external_ref')

        try:
            adapter = self.adapter
            result = adapter.unlink_existing_webhooks(external_ids)
        except Exception as ex:
            if ex.args:
                result = ex.args[0]
            _logger.error(ex)
        finally:
            self.webhook_line_ids.unlink()

        return result

    def create_integration_webhook_lines(self, data_dict):
        vals_list = list()
        default_vals = {
            'integration_id': self.id,
            'original_base_url': self._get_base_url_or_debug(),
        }

        for (controller_method, name, technical_name), reference in data_dict.items():
            vals = {
                'name': name,
                'technical_name': technical_name,
                'controller_method': controller_method,
                'external_ref': reference,
                **default_vals,
            }
            vals_list.append(vals)

        self.webhook_line_ids.unlink()
        return self.env['integration.webhook.line'].create(vals_list)

    def prepare_webhook_routes(self):
        result = dict()
        routes = self._retrieve_webhook_routes()

        for controller_method, names in routes.items():
            for name_tuple in names:
                route = self._build_webhook_route(controller_method)
                key_tuple = (controller_method,) + name_tuple
                result[key_tuple] = route

        return result

    @ormcache()
    def get_base_url_config(self):
        """
        Copy of method from model.py
        """
        value = self[:1].get_base_url()
        return value.strip('/')

    def _get_base_url_or_debug(self):
        debug_url = config.options.get('localhost_debug_url')
        if debug_url:
            return debug_url  # Fake url, just for localhost coding and bedug
        return self.get_base_url_config()

    def _build_webhook_route(self, controller_method):
        db_name = self.env.cr.dbname
        base_url = self._get_base_url_or_debug()
        return f'{base_url}/{db_name}/integration/{self.type_api}/{self.id}/{controller_method}'

    def _retrieve_webhook_routes(self):
        _logger.error('Webhook routes are not specified for the "%s".', self.name)
        return dict()

    def _get_configuration_postfix(self):
        self.ensure_one()
        return self.type_api

    def _get_ecommerce_system_name(self):
        """
        Get human-readable name of the e-commerce system.
        Returns the display name from type_api selection field.
        """
        self.ensure_one()

        for value, label in self._fields['type_api'].selection:
            if value == self.type_api:
                return label

        return self.type_api  # Fallback to technical name if not found

    def action_active(self):
        self.ensure_one()

        self._raise_if_not_access_granted()

        self.action_test_connection(raise_success=False)
        self.state = 'active'

    def action_draft(self):
        self.ensure_one()
        self.state = 'draft'

    def action_open_shop(self):
        return {
            'type': 'ir.actions.act_url',
            'url': self.adapter.admin_url,
            'target': 'new',
        }

    def action_test_connection(self, raise_success=True):
        # TODO: Deprecated? We have special wizard for this now.
        self.ensure_one()
        self._ensure_settings()

        try:
            # Attempt to build the adapter and check the connection
            wizard = self.create_auth_wizard()
            connection_ok = wizard._build_and_test_client_from_wizard()
        except Exception as e:
            # Catch any exception and raise a more user-friendly error message
            raise UserError(_(
                'Connection test failed due to an unexpected error.\n\n'
                'Error: %s\n\n'
                'Please verify your connection settings (e.g., API keys, URLs, and credentials) and try again. '
                'If the problem persists, please contact support.'
            ) % str(e)) from e

        if connection_ok:
            if raise_success:
                message = _("Connection test successful! Your connection to the e-commerce store is working correctly.")
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'message': message,
                        'type': 'success',
                        'sticky': False,
                    }
                }
        else:
            # Raise a user-friendly message for connection failure
            raise UserError(_(
                'Connection test failed.\n\n'
                'Please verify your connection settings (e.g., API keys, URLs, and credentials) and try again. '
                'If the problem persists, please contact support.'
            ))

    def action_import_orders(self):
        self.ensure_one()
        self._raise_if_not_access_granted()

        self.import_orders()

    def _raise_if_not_access_granted(self):
        if not self.api_access_granted:
            raise UserError(_(
                'Please complete the authentication process before you begin setting up data synchronization.'
            ))

    def is_integration_cancel_allowed(self):
        """Currently it's a Shopify only feature"""
        return False

    def _get_cancel_order_view_id(self):
        """Specific for every integration"""
        return False

    def _ensure_settings(self):
        """Hook method for redefining"""
        pass

    def action_view_all_external_orders_data(self):
        """
        Open view with all integration files. Used on kanban card.
        """
        return {
            'type': 'ir.actions.act_window',
            'name': 'External Orders',
            'res_model': 'sale.integration.input.file',
            'view_mode': 'list,form',
            'domain': [('si_id', '=', self.id)],
            'target': 'current',
        }

    def action_view_queued_or_failed_external_orders_data(self):
        """
        Open view with all queued or failed integration files. Used on kanban card.
        """
        return {
            'type': 'ir.actions.act_window',
            'name': 'Queued or Failed Orders',
            'res_model': 'sale.integration.input.file',
            'view_mode': 'list,form',
            'domain': [
                ('si_id', '=', self.id),
            ],
            'target': 'current',
            'context': {
                'search_default_without_sales_order': True,
            },
        }

    @property
    def is_active(self):
        return self.state == 'active'

    @property
    def is_order_import_enabled(self):
        """
        Check if order import is enabled for this integration.
        Returns True only when the integration is active AND receive_orders_cron_id_active is True.
        """
        return self.is_active and self.receive_orders_cron_id_active

    @property
    def is_periodic_inventory_sync_enabled(self):
        """
        Check if periodic inventory synchronization is enabled for this integration.
        Returns True only when the integration is active AND inventory_synchronization_cron_id_active is True.
        Note: This is for scheduled/periodic sync, not real-time inventory updates.
        """
        return self.is_active and self.inventory_synchronization_cron_id_active

    @property
    def is_real_time_inventory_export_enabled(self):
        """
        Check if real-time inventory export is enabled for this integration.
        Returns True only when the integration is active AND export_inventory_job_enabled is True.
        Note: This is for real-time sync on stock changes, not periodic/scheduled sync.
        """
        return self.is_active and self.export_inventory_job_enabled

    @property
    def is_product_template_export_enabled(self):
        """
        Check if product template export is enabled for this integration.
        Returns True only when the integration is active AND export_template_job_enabled is True.
        """
        return self.is_active and self.export_template_job_enabled

    @property
    def is_order_tracking_export_enabled(self):
        """
        Check if order tracking export is enabled for this integration.
        Returns True only when the integration is active AND export_tracking_job_enabled is True.
        """
        return self.is_active and self.export_tracking_job_enabled

    @property
    def is_sale_order_status_export_enabled(self):
        """
        Check if sale order status export is enabled for this integration.
        Returns True only when the integration is active AND export_sale_order_status_job_enabled is True.
        """
        return self.is_active and self.export_sale_order_status_job_enabled

    @property
    def is_installed_sale_product_configurator(self):
        return self.is_module_installed('sale_product_configurator')

    @property
    def allow_bundle_creation(self):
        return self.product_bundle_policy == 'create_bundle'

    @property
    def adapter(self):
        self.ensure_one()
        return self._build_adapter()

    def advanced_inventory(self):
        """Using external multi source locations"""
        return False

    def _update_crons_activity(self):
        for record in self:
            if not record.receive_orders_cron_id:
                record._create_receive_orders_cron()

            if not record.inventory_synchronization_cron_id:
                record._create_inventory_cron()

    def _get_cron_name(self, action_name):
        """
        Generate a standardized cron name for e-commerce integrations.

        Args:
            action_name (str): The action description (e.g., "Import Orders", "Periodic Inventory Sync")

        Returns:
            str: Formatted cron name in the format:
                 [E-Commerce Integration] {ecommerce_system} - {integration_name}: {action_name}
        """
        self.ensure_one()
        ecommerce_name = self._get_ecommerce_system_name()
        return f'[E-Commerce Integration] {ecommerce_name} - {self.name}: {action_name}'

    def _create_receive_orders_cron(self):
        self.ensure_one()

        cron = self.sudo().env['ir.cron'].create({
            'active': False,
            'name': self._get_cron_name('Import Orders'),
            'model_id': self.env.ref('integration.model_sale_integration').id,
            'interval_type': 'minutes',
            'interval_number': 5,
            'code': f'model.browse({self.id}).integration_receive_orders_cron()',
            'user_id': SUPERUSER_ID,
        })
        self.with_context(skip_write_actions=True).receive_orders_cron_id = cron.id

    def _create_inventory_cron(self):
        self.ensure_one()

        # Calculating time in UTC for nextcall in 00:00:000 by users time zone
        tz = self.env.user.tz and pytz.timezone(self.env.user.tz) or pytz.utc
        now_user = datetime.now(tz=tz).replace(minute=0, second=0, tzinfo=None)
        now_utc = datetime.now().replace(minute=0, second=0)
        diff = now_user - now_utc
        nextcall = now_utc.replace(hour=0) - diff + timedelta(days=1)

        cron = self.sudo().env['ir.cron'].create({
            'active': False,
            'name': self._get_cron_name('Periodic Inventory Sync'),
            'model_id': self.env.ref('integration.model_sale_integration').id,
            'interval_type': 'days',
            'interval_number': 1,
            'code': f'model.browse({self.id}).integrationApiExportInventory()',
            'nextcall': nextcall.strftime('%Y-%m-%d %H:%M:%S'),
            'user_id': SUPERUSER_ID,
        })
        self.with_context(skip_write_actions=True).inventory_synchronization_cron_id = cron.id

    def _update_cron_names(self):
        """
        Update cron names when integration name or e-commerce system changes.
        This ensures cron names always reflect the current integration name.
        """
        for rec in self:
            # Update receive orders cron name
            if rec.receive_orders_cron_id:
                rec.receive_orders_cron_id.sudo().name = rec._get_cron_name('Import Orders')

            # Update inventory sync cron name
            if rec.inventory_synchronization_cron_id:
                rec.inventory_synchronization_cron_id.sudo().name = rec._get_cron_name('Periodic Inventory Sync')

    def get_class(self):
        """It's just a stub."""
        return NoAPIClient

    @api.model
    def get_integrations(self, job_name, company_id=False):
        domain = [('state', '=', 'active')]

        if job_name:
            domain.append((f'{job_name}_job_enabled', '=', True))

        if company_id:
            domain.append(('company_id', '=', company_id))

        return self.search(domain)

    @api.model
    def get_active_integrations(self):
        integrations = self.search([('state', '=', 'active')])
        return [{'id': x.id, 'name': x.name} for x in integrations]

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._post_create()

        return records

    def _post_create(self):
        for rec in self:
            # Write settings fields
            rec.write_settings_fields()

            # Handle ecommerce fields
            rec.create_fields_mapping_for_integration()
            rec._set_default_advanced_fields(force=True)

            # Update crons
            rec._update_crons_activity()

    # TODO: Move these lists to constants or method?
    @track_changes(
        include_related_fields=[
            'field_ids',
            'location_line_ids',
            'order_metafield_mapping_ids',
            'customer_metafield_mapping_ids',
            'external_order_field_mapping_ids',
        ],
        sensitive_fields=['key', 'consumer_key', 'consumer_secret', 'wp_app_password'],
        exclude_fields=[
            'last_receive_orders_datetime',
            'last_order_sync_datetime',
            'last_update_pricelist_items',
            'orders_last_7_days_chart_data_cache',
        ],
    )
    def write(self, vals):
        result = super().write(vals)

        if not self:
            return result

        # Invalidate integration cache if any essential field was changed
        if any(getattr(self._fields[f], 'invalidate_integration_cache', False) for f in vals.keys()):
            self.increment_sync_token()

        # Skip rest of the logic if skip_write_actions is set
        if self.env.context.get('skip_write_actions'):
            return result

        # 1. Unlink/create/modify the essential fields if `type_api` was changed
        if 'type_api' in vals:
            # 1.1 Unlink
            self._pre_unlink()

            # 1.2 Create
            self._post_create()

            # 1.3 Modify values if needed
            if vals['type_api'] not in ('prestashop', 'shopify'):
                vals['validate_barcode'] = False

        # 2. Write settings fields
        self.write_settings_fields()

        # 3. Update advanced fields
        if 'change_advanced_fields' in vals:
            if self.change_advanced_fields:
                self._set_default_advanced_fields()
            else:
                self._set_default_advanced_fields(force=True)

        # 4. Update crons activity
        if 'state' in vals:
            self._update_crons_activity()

        # 5. Update cron names if integration name or type_api changed
        if 'name' in vals:
            self._update_cron_names()

        # 6. Normalize dependency fields
        if INVENTORY_DEPENDENT_FIELDS & set(vals):
            self._update_inventory_field_values()

        return result

    def unlink(self):
        self._pre_unlink()

        return super(SaleIntegration, self).unlink()

    def _pre_unlink(self):
        for rec in self.sudo():
            rec.drop_webhooks()

            rec.field_ids.unlink()

            crons = (
                rec.receive_orders_cron_id
                | rec.inventory_synchronization_cron_id
                | rec.export_prices_cron_id
            ).exists()
            if crons:
                crons.unlink()

            rec.env['product.ecommerce.field.mapping'] \
                .search([('integration_id', '=', rec.id)]).unlink()

    def _valid_field_parameter(self, field, name):
        # Allow the `invalidate_integration_cache` parameter to avoid Odoo warnings
        return name == 'invalidate_integration_cache' or super()._valid_field_parameter(field, name)

    def _update_inventory_field_values(self):
        """
        Normalize inventory-related fields to maintain logical consistency after write.

        Rules:
        - If 'update_stock_for_manufacture_boms' is disabled, 'allow_multi_company_inventory_calculation'
        must also be disabled.
        - If both 'export_inventory_job_enabled' and 'inventory_synchronization_cron_id_active'
        are disabled, 'update_stock_for_manufacture_boms' is automatically disabled.
        """
        for rec in self:
            updates = {}

            # Rule 1: If BOM update is disabled → disable multi-company inventory calculation
            if not rec.update_stock_for_manufacture_boms and rec.allow_multi_company_inventory_calculation:
                updates['allow_multi_company_inventory_calculation'] = False

            # Rule 2: If both inventory sync flags are disabled → disable BOM update
            if not rec.export_inventory_job_enabled and not rec.inventory_synchronization_cron_id_active:
                if rec.update_stock_for_manufacture_boms:
                    updates['update_stock_for_manufacture_boms'] = False

            if updates:
                rec.with_context(skip_write_actions=True).write(updates)

    def create_fields_mapping_for_integration(self):
        self.ensure_one()

        field_ids = self.env['product.ecommerce.field'].search([
            ('is_default', '=', True),
            ('is_private', '=', False),
            ('type_api', '=', self.type_api),
        ])

        for field in field_ids:
            field._ensure_mapping(self.id, mark_active=False)

        return True

    def write_settings_fields(self):
        self.ensure_one()

        res = True
        settings_fields = self._convert_settings_fields_to_dict()

        exists_fields = self.field_ids.mapped('name')

        fields_list_to_add = [
            (0, 0, {
                'name': field_name,
                'description': field['description'],
                'value': str(field['value']),
                'eval': field['eval'],
                'is_secure': field['is_secure'],
            })
            for field_name, field in settings_fields.items()
            if field_name not in exists_fields
        ]

        if fields_list_to_add:
            res = self \
                .with_context(skip_write_actions=True) \
                .write({'field_ids': fields_list_to_add})

        return res

    def get_settings_value(self, key, default_value=None):
        self.ensure_one()
        field = self.get_settings_field(key, default_value is None)

        if not field:
            return default_value

        value = field.value
        if value and field.eval:
            value = safe_eval(value)
        return value

    def set_settings_value(self, key, value, to_string=False):
        self.ensure_one()
        if to_string:
            value = str(value)
        field = self.get_settings_field(key)
        field.value = value

    def get_settings_field(self, key, raise_error=True):
        self.ensure_one()

        field = self.field_ids.filtered(lambda x: x.name == key)
        if field:
            return field

        # If field was not found the first time can be that this
        # is new setting and we need to add default value
        self.write_settings_fields()

        field = self.field_ids.filtered(lambda x: x.name == key)

        if not field and raise_error:
            raise UserError(_(
                'The settings field with the key "%s" is missing.\n\n'
                'This issue may have been caused by recent changes to the settings, such as accidentally removing '
                'the field. Please re-add the field manually in the General tab of the integration settings.\n\n'
                'If you are unsure how to resolve this or the issue persists, please contact '
                'support: https://support.ventor.tech/'
            ) % key)

        return field

    def _ensure_not_null_setting(self, key_list: list):
        result = list()

        for key in key_list:
            field = self.get_settings_field(key, raise_error=False)

            if not field.value:
                raise UserError(_(
                    'The "%s" settings field is required for the integration "%s".\n\n'
                    'Please go to the "Quick Configuration" wizard in the integration settings to complete '
                    'the connection setup. Ensure that all required fields are filled in properly for '
                    'the integration to function correctly.\n\n'
                    'If you are unsure how to resolve this or the issue persists, please contact '
                    'support: https://support.ventor.tech/'
                ) % (key, self.name))

            result.append(field.value)

        return result

    def get_hash(self, settings=None):
        if settings:
            return hash(str(settings))
        return hash(str(self.to_dictionary()))

    def increment_sync_token(self):
        field = self.get_settings_field('adapter_version')
        field.value = str(time())
        return field.value

    def invalidate_integration_cache(self, erase_config_wizard: bool = True):
        for rec in self.with_context(skip_write_actions=True):
            rec.increment_sync_token()

            if erase_config_wizard:
                integration_postfix = rec._get_configuration_postfix()

                rec.env['configuration.wizard.' + integration_postfix].search([
                    ('integration_id', '=', rec.id),
                ]).unlink()

    def _truncate_settings_url(self):
        self.ensure_one()
        full_settings_url = self.get_settings_value('url')

        # Cut off `https://`
        settings_url_list = full_settings_url.strip('/').split('//')
        settings_url = settings_url_list[-1]

        # Get `host` only
        settings_url_list = settings_url.split('/')
        settings_url = settings_url_list[0]

        if settings_url.startswith('www.'):
            settings_url = settings_url.lstrip('www.')
        return settings_url

    def _convert_external_tax(self, tax_id):
        """Expected its own implementation for each integration."""
        return False

    def _convert_settings_fields_to_dict(self):
        # 1. Get default settings fields from adapter class
        settings_fields = getattr(self.get_class(), 'settings_fields', None)

        # 2. Convert settings fields to dict
        return {
            field[0]: {
                'name': field[0],
                'description': field[1],
                'value': field[2],
                'eval': field[3] if len(field) > 3 else False,
                'is_secure': field[4] if len(field) > 4 else False,
            }
            for field in (settings_fields or [])
        }

    def get_external_block_limit(self):
        return IMPORT_EXTERNAL_BLOCK

    def get_integration_location(self):
        self.ensure_one()

        if not self.location_line_ids:
            wh_ids = self.env['stock.warehouse'].search([
                ('company_id', '=', self.company_id.id)
            ])
            return wh_ids.mapped('lot_stock_id')

        return self.location_line_ids.mapped('erp_location_id')

    def initial_import_attributes(self, remove_existing_records=False):
        external_attributes = self.integrationApiImportAttributes(remove_existing_records=remove_existing_records)
        self.integrationApiImportAttributeValues(remove_existing_records=remove_existing_records)

        return external_attributes

    def initial_import_countries(self, remove_existing_records=False):
        external_countries = self.integrationApiImportCountries(remove_existing_records=remove_existing_records)

        self.integrationApiImportStates(remove_existing_records=remove_existing_records)

        return external_countries

    def import_master_data_in_background(self, entities=None, remove_existing_records=False):
        """
        This method creates background jobs for importing master data and return list of jobs.

        Args:
            entities: Optional list of integration.import.entity records to import.
                     If None, imports all available entities for the integration type.

        Returns:
            recordset: List of created queue jobs.
        """
        self.ensure_one()

        name = self.name
        self = self.with_context(company_id=self.company_id.id)

        jobs = self.env['queue.job']
        context = {
            'job_integration_id': self.id,
            'job_integration_job_type': 'initial_import',
        }

        # Get entities to import
        if entities is None:
            # Import all entities available for this integration type
            domain = [
                '|',
                ('integration_type', '=', False),
                ('integration_type', '=', self.type_api),
                ('is_master_data', '=', True),
            ]
            entities = self.env['integration.import.entity'].search(domain, order='name asc')
        else:
            # Use provided entities
            entities = entities.filtered(
                lambda e: not e.integration_type or e.integration_type == self.type_api)

        # Create jobs for each entity
        for entity in entities:
            if not entity.method_name:
                _logger.warning(
                    f'Method "{entity.method_name}" not found on integration, '
                    f'skipping entity "{entity.name}".'
                )
                continue

            delayed = self.with_context(**context).with_delay(
                description=f'{name}: Initial Import. {entity.name}',
                priority=2,
            )
            delayed_method = getattr(delayed, entity.method_name)
            job = delayed_method(remove_existing_records=remove_existing_records)
            jobs |= job.db_record() if isinstance(job, Job) else job

        return jobs

    def import_master_data(self, entities=None, remove_existing_records=False):
        """
        This method imports master data synchronously (real-time) and returns the results.

        Args:
            entities: Optional list of integration.import.entity records to import.
                     If None, imports all available entities for the integration type.

        Returns:
            dict: Dictionary with import results for each entity.
        """
        self.ensure_one()

        name = self.name
        self = self.with_context(company_id=self.company_id.id)

        results = {}

        # Get entities to import
        if entities is None:
            # Import all entities available for this integration type
            domain = [
                '|',
                ('integration_type', '=', False),
                ('integration_type', '=', self.type_api),
                ('is_master_data', '=', True),
            ]
            entities = self.env['integration.import.entity'].search(domain, order='name asc')
        else:
            # Use provided entities
            entities = entities.filtered(
                lambda e: not e.integration_type or e.integration_type == self.type_api)

        # Import each entity synchronously
        for entity in entities:
            if not entity.method_name:
                _logger.warning(f'Entity "{entity.name}" has no method_name defined, skipping.')
                results[entity.name] = {'status': 'skipped', 'reason': 'No method_name defined'}
                continue

            method = getattr(self, entity.method_name, None)
            if not method:
                _logger.warning(
                    f'Method "{entity.method_name}" not found on integration, '
                    f'skipping entity "{entity.name}".'
                )
                results[entity.name] = {
                    'status': 'skipped',
                    'reason': f'Method {entity.method_name} not found'
                }
                continue

            try:
                _logger.info(f'{name}: Importing {entity.name} synchronously...')
                result = method(remove_existing_records=remove_existing_records)
                results[entity.name] = {'status': 'success', 'result': result}
                _logger.info(f'{name}: Successfully imported {entity.name}')
            except Exception as e:
                _logger.error(f'{name}: Failed to import {entity.name}: {str(e)}')
                results[entity.name] = {'status': 'error', 'error': str(e)}

        return results

    def import_products_in_background(self, external_ids=None, remove_existing_records=False):
        """
        This method creates background jobs for importing products and returns list of jobs.

        Args:
            external_ids: Optional list of external product IDs to import.
                        If None, imports all available products from the e-commerce system.
            remove_existing_records: If True, removes existing external records before import.

        Returns:
            recordset: List of created queue jobs.
        """
        self.ensure_one()

        name = self.name
        self = self.with_context(company_id=self.company_id.id)

        # Remove existing records if requested (do this once at the beginning)
        if remove_existing_records:
            ExternalTemplate = self.env['integration.product.template.external']

            existing_templates = ExternalTemplate.search([('integration_id', '=', self.id)])

            if existing_templates:
                existing_templates.unlink()

            _logger.info(
                f'{name}: Removed {len(existing_templates)} existing templates '
                '(variants removed automatically via cascade).'
            )

        jobs = self.env['queue.job']

        # Get product template IDs to import
        if external_ids is None:
            # Import all products available from the e-commerce system
            template_ids = self.adapter.get_product_template_ids()
        else:
            # Use provided external IDs
            template_ids = external_ids

        if not template_ids:
            _logger.warning(f'{name}: No products found to import.')
            return jobs

        # Create jobs for importing products in blocks
        block = 1
        limit = self.get_external_block_limit()
        description_ = (
            f'{name}: Products Import: Import Products Batch '
            '(create external records + auto-matching) [Block %s]'
        )
        context = {
            'job_integration_id': self.id,
            'job_integration_job_type': 'product',
        }

        while template_ids:
            job = self.with_context(**context).with_delay(
                priority=2,
                description=(description_ % block),
            ).import_external_product(template_ids[:limit])

            jobs |= job.db_record() if isinstance(job, Job) else job

            block += 1
            template_ids = template_ids[limit:]

        return jobs

    def import_products(self, external_ids=None, remove_existing_records=False):
        """
        This method imports products in real-time and returns the results.

        Args:
            external_ids: Optional list of external product IDs to import.
                        If None, imports all available products from the e-commerce system.
            remove_existing_records: If True, removes existing external records before import.

        Returns:
            dict: Dictionary with import results including success/error counts and details.
        """
        self.ensure_one()

        name = self.name
        self = self.with_context(company_id=self.company_id.id)

        # Remove existing records if requested (do this once at the beginning)
        if remove_existing_records:
            ExternalTemplate = self.env['integration.product.template.external']

            existing_templates = ExternalTemplate.search([('integration_id', '=', self.id)])

            if existing_templates:
                existing_templates.unlink()

            _logger.info(
                f'{name}: Removed {len(existing_templates)} existing templates '
                '(variants removed automatically via cascade).'
            )

        results = {
            'total_processed': 0,
            'successful_imports': 0,
            'failed_imports': 0,
            'errors': [],
            'imported_templates': [],
            'imported_variants': []
        }

        # Get product template IDs to import
        if external_ids is None:
            # Import all products available from the e-commerce system
            template_ids = self.adapter.get_product_template_ids()
        else:
            # Use provided external IDs
            template_ids = external_ids

        if not template_ids:
            _logger.warning(f'{name}: No products found to import.')
            results['message'] = 'No products found to import.'
            return results

        _logger.info(f'{name}: Starting real-time import of {len(template_ids)} products...')

        # Import products in blocks to avoid memory issues
        limit = self.get_external_block_limit()
        total_blocks = (len(template_ids) + limit - 1) // limit

        db_registry = Registry(self.env.cr.dbname)

        for block_num in range(total_blocks):
            start_idx = block_num * limit
            end_idx = start_idx + limit
            block_template_ids = template_ids[start_idx:end_idx]

            _logger.info(
                f'{name}: Processing block {block_num + 1}/{total_blocks} '
                'with {len(block_template_ids)} products'
            )

            # Use a separate cursor for each block to isolate transactions:
            # if an error occurs during processing, only the current block is rolled back,
            # while previously processed blocks remain committed.
            with db_registry.cursor() as new_cr:
                new_env = api.Environment(new_cr, self.env.uid, {})
                new_integration = new_env['sale.integration'].browse(self.id)

                try:
                    # Use the internal import method directly
                    external_templates, external_variants, error_list, __ = new_integration._import_external_product(
                        block_template_ids,
                    )

                    # FIXME: _import_external_product can't correctly process incorrect external IDs which leads
                    # to empty errors list, so we can't later show them in the UI.

                    # Update results with actual data
                    results['successful_imports'] += len(external_templates) + len(external_variants)
                    results['failed_imports'] += len(error_list)
                    results['total_processed'] += len(block_template_ids)

                    # Add imported templates and variants
                    if external_templates:
                        for template in external_templates:
                            results['imported_templates'].append({
                                'name': template.name,
                                'code': template.code,
                                'external_reference': template.external_reference,
                            })

                    if external_variants:
                        for variant in external_variants:
                            results['imported_variants'].append({
                                'name': variant.name,
                                'code': variant.code,
                                'external_reference': variant.external_reference,
                            })

                    # Add errors
                    if error_list:
                        results['errors'].extend(error_list)

                except Exception as e:
                    _logger.error(f'{name}: Failed to import block {block_num + 1}: {str(e)}')
                    results['failed_imports'] += len(block_template_ids)
                    results['errors'].append(f'Block {block_num + 1}: {str(e)}')
                    results['total_processed'] += len(block_template_ids)

                    # Rollback to clear any partial changes in this block
                    new_cr.rollback()

        _logger.info(
            f'{name}: Completed synchronous import. Processed: {results["total_processed"]}, '
            f'Successful: {results["successful_imports"]}, Failed: {results["failed_imports"]}'
        )

        return results

    @expose_for_testing('Import Master Data')
    def integrationApiImportData(self):
        self.import_master_data_in_background()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Initial Import'),
                'message': 'Import master data jobs are created',
                'type': 'success',
                'sticky': False,
            }
        }

    def action_import_master_data(self):
        return self.integrationApiImportData()

    def action_import_related_products(self):
        adapter = self.adapter
        # Fetch data.
        adapter_products, template_router = adapter.get_products_for_accessories()

        model_name = 'product.template'
        ProductTemplateExternal = self.env[f'integration.{model_name}.external']
        ProductTemplateMapping = self.env[f'integration.{model_name}.mapping']
        mappings = self.env[f'integration.{model_name}.mapping']
        internal_field_name, external_field_name = ProductTemplateMapping._mapping_fields
        MessageWizard = self.env['message.wizard']

        # Create / update external and mappings.
        for product in adapter_products:
            name = product['name']
            # Get translation if name contains different languages
            if isinstance(name, dict) and name.get('language'):
                original, __ = ProductTemplateExternal.get_original_and_translation(name, self)

                if original:
                    name = original

            external_record = ProductTemplateExternal.create_or_update({
                'integration_id': self.id,
                'code': product['id'],
                'name': name,
                'external_reference': product.get('external_reference'),
            })
            external_record._post_import_external_one(product)

            mapping = ProductTemplateMapping.search([
                ('integration_id', '=', self.id),
                (external_field_name, '=', external_record.id),
            ])
            if not mapping:
                mapping = ProductTemplateMapping.create({
                    'integration_id': self.id,
                    external_field_name: external_record.id,
                })

            mappings |= mapping

        if not mappings:
            return MessageWizard.create_and_run(_('No related products to synchronize.'))

        mappings_to_fix = mappings.filtered(lambda x: not getattr(x, internal_field_name))

        # Fix unmapped records if necessary. Format message.
        if mappings_to_fix:
            message = _(
                'Some of the related products are not yet synchronised to Odoo or not yet mapped '
                'to corresponding Odoo Products so it is not possible to import them. '
                'Please, make sure to launch products synchronisation again and make sure '
                'to map products in menu "Mappings → Products" '
                '(or create them in Odoo by clicking "Import Products" button in the same menu):'
            )
            mapping_names = mappings_to_fix.mapped(f'{external_field_name}.display_name')

            html_message = f'<div>{message}</div>'
            html_names = f'<ul>{"".join([f"<li>{x}</li>" for x in mapping_names])}</ul>'

            message_wizard = MessageWizard.create({
                'message': str(mappings_to_fix.ids),
                'export_html': html_message + '<br/>' + html_names,
            })
            return message_wizard.run_wizard('integration_message_wizard_form_mapping_product')

        # Assign related products to the parent product.
        templates = self.env[model_name]
        for template_external_id, related_products_ids in template_router.items():
            template = templates.from_external(self, template_external_id, False)

            optional_product_ids = self.env[model_name]
            for product_id in related_products_ids:
                optional_product_ids |= templates.from_external(self, product_id, False)

            template.optional_product_ids = [(6, 0, optional_product_ids.ids)]
            templates |= template

        # Summary. Format message.
        mapping_names = list()
        base_url = self.get_base_url_config()
        pattern = (
            '<a href="%s/web#id=%s&model=%s&view_type=form" target="_blank">%s</a>'
        )

        def _format_optional_products(template):
            names = template.optional_product_ids.mapped('name')
            html_names = f'<ul>{"".join([f"<li>{x}</li>" for x in names])}</ul>'
            template_name = pattern % (base_url, template.id, model_name, template.name)
            return f'<li>{template_name + html_names}</li>'

        for template in templates:
            mapping_names.append(
                _format_optional_products(template)
            )

        message = _('The Products were synchronized:\n%s') % (f'<ul>{"".join(mapping_names)}</ul>')
        return MessageWizard.create_html_and_run(message)

    @expose_for_testing('Import Delivery (Shipping) Methods')
    def integrationApiImportDeliveryMethods(self, remove_existing_records=False):
        external_records, adapter_external_data = self._import_external(
            'integration.delivery.carrier.external',
            'get_delivery_methods',
            remove_existing_records=remove_existing_records,
        )
        external_records._map_external(adapter_external_data)
        return external_records

    @expose_for_testing('Import Taxes')
    def integrationApiImportTaxes(self, remove_existing_records=False):
        external_records, adapter_external_data = self._import_external(
            'integration.account.tax.external',
            'get_taxes',
            remove_existing_records=remove_existing_records,
        )
        external_records._map_external(adapter_external_data)
        return external_records

    @expose_for_testing('Import Payment Methods')
    def integrationApiImportPaymentMethods(self, remove_existing_records=False):
        external_records, adapter_external_data = self._import_external(
            'integration.sale.order.payment.method.external',
            'get_payment_methods',
            remove_existing_records=remove_existing_records,
        )
        external_records._map_external(adapter_external_data)
        return external_records

    @expose_for_testing('Import Languages')
    def integrationApiImportLanguages(self, remove_existing_records=False):
        external_records, adapter_external_data = self._import_external(
            'integration.res.lang.external',
            'get_languages',
            remove_existing_records=remove_existing_records,
        )
        external_records._map_external(adapter_external_data)
        return external_records

    @expose_for_testing('Import Attributes')
    def integrationApiImportAttributes(self, remove_existing_records=False):
        external_records, adapter_external_data = self._import_external(
            'integration.product.attribute.external',
            'get_attributes',
            remove_existing_records=remove_existing_records,
        )
        external_records._map_external(adapter_external_data)
        return external_records

    @expose_for_testing('Import Attribute Values')
    def integrationApiImportAttributeValues(self, remove_existing_records=False):
        external_records, adapter_external_data = self._import_external(
            'integration.product.attribute.value.external',
            'get_attribute_values',
            remove_existing_records=remove_existing_records,
        )
        external_records._map_external(adapter_external_data)
        return external_records

    @expose_for_testing('Import Locations')
    def integrationApiImportLocations(self, remove_existing_records=False):
        external_records, __ = self._import_external(
            'integration.stock.location.external',
            'get_locations',
            remove_existing_records=remove_existing_records,
        )
        return external_records

    @expose_for_testing('Import Countries')
    def integrationApiImportCountries(self, remove_existing_records=False):
        external_records, adapter_external_data = self._import_external(
            'integration.res.country.external',
            'get_countries',
            remove_existing_records=remove_existing_records,
        )
        external_records._map_external(adapter_external_data)
        return external_records

    @expose_for_testing('Import States')
    def integrationApiImportStates(self, remove_existing_records=False):
        external_records, adapter_external_data = self._import_external(
            'integration.res.country.state.external',
            'get_states',
            remove_existing_records=remove_existing_records,
        )
        external_records._map_external(adapter_external_data)
        return external_records

    @expose_for_testing('Import Categories')
    def integrationApiImportCategories(self, remove_existing_records=False):
        external_records, adapter_external_data = self._import_external(
            'integration.ecommerce.product.category.external',
            'get_categories',
            remove_existing_records=remove_existing_records,
        )
        external_records._map_external(adapter_external_data)
        return external_records

    @expose_for_testing('Import Sale Order Statuses')
    def integrationApiImportSaleOrderStatuses(self, remove_existing_records=False):
        external_records, adapter_external_data = self._import_external(
            'integration.sale.order.sub.status.external',
            'get_sale_order_statuses',
            remove_existing_records=remove_existing_records,
        )
        external_records._map_external(adapter_external_data)
        return external_records

    @expose_for_testing('Import Products')
    def integrationApiImportProducts(self, external_ids=None):
        block = 1
        limit = self.get_external_block_limit()
        template_ids = external_ids or self.adapter.get_product_template_ids()

        context = {
            'company_id': self.company_id.id,
            'job_integration_id': self.id,
            'job_integration_job_type': 'product',
        }
        self = self.with_context(**context)

        description_ = (
            f'{self.name}: Initial Products Import: Import Products Batch '
            '(create external records + auto-matching) [block %s]'
        )
        while template_ids:
            self.with_delay(
                priority=2,
                description=(description_ % block),
            ).import_external_product(template_ids[:limit])

            block += 1
            template_ids = template_ids[limit:]

    def import_customers(self, external_ids=None, remove_existing_records=False):
        # TODO: Customer import should be implemented in a way like other entities import works
        # - Import external records and create mappings
        # - Create/update partners and addresses
        # Current implementation is just workaround to make it compatible with other entities import
        if remove_existing_records:
            self.env['integration.res.partner.external'].search([
                ('integration_id', '=', self.id),
            ]).unlink()

        if external_ids and not isinstance(external_ids, list):
            external_ids = [external_ids]

        if not external_ids:
            # TODO: Use cut off date for customers?
            external_ids = self.adapter.get_customer_ids()

        imported_customers = self.env['integration.res.partner.external']
        for external_id in external_ids:
            customer_records = self.import_single_customer(external_id)
            contact_records = customer_records.filtered(lambda r: r.type == 'contact')
            external_customer_ids = contact_records.mapped('external_customer_ids')
            imported_customers |= external_customer_ids

        return imported_customers

    def import_all_customers(self):
        # TODO: Implement this method
        pass

    @expose_for_testing('Import Customer by ID')
    def integrationApiImportSingleCustomer(self):
        if not self.test_method_parameter:
            return False

        customer_records = self.import_single_customer(self.test_method_parameter)
        return customer_records

    @expose_for_testing('Print Integration Configuration Fields')
    def integrationApiPrintFields(self):
        # TODO: Deprecated? We have Import/Export wizard now.
        params = self.to_dictionary()
        params = json.dumps(params, indent=4, default=str)
        raise UserError(str(params))

    @expose_for_testing('Print Order Import Parameters')
    def integrationApiReceiveOrdersKwargs(self):
        kwargs = self.adapter.order_fetch_kwargs()
        raise UserError(str(kwargs))

    def import_orders(self, external_ids=None, remove_existing_records=False):
        """
        Import orders by external IDs or all recent orders.

        Important: this is internal method, so it does not check if orders import is enabled.

        Args:
            external_ids (list): List of external order IDs to import.
            remove_existing_records (bool): Whether to remove existing records.
        Returns:
            list: List of external orders (input files).
        """
        self.ensure_one()

        if remove_existing_records:
            self.env['sale.integration.input.file'].search([
                ('si_id', '=', self.id),
            ]).unlink()

        if external_ids and not isinstance(external_ids, list):
            external_ids = [external_ids]

        if not external_ids:
            return self._import_recent_orders()

        imported_orders = self.env['sale.integration.input.file']
        for external_id in external_ids:
            imported_orders |= self.with_context(skip_create_order_from_input=True) \
                .fetch_order_by_id(external_id, raise_error=True)

        return imported_orders

    def _import_recent_orders(self):
        """
        Import recent orders from the external system (based on date parameters from the integration).
        By recent orders we mean orders that were created or updated after the last receive datetime.

        This method shouldn't be used to import all orders from the external system
        (or import a large number of orders). Use integrationApiImportOrders instead to import
        orders as background jobs.

        Returns:
            list: List of external orders (input files).
        """
        self.ensure_one()

        adapter = self.adapter

        _logger.info(
            '%s (import orders): from kwargs %s',
            self.name,
            adapter.order_fetch_kwargs(),
        )

        self.last_order_sync_datetime = fields.Datetime.now()

        new_input_files = self.env['sale.integration.input.file']
        filtered_external_orders_count = 0
        last_receive_dt = self.last_receive_orders_datetime
        while True:
            # Import batch of orders
            external_orders = adapter.receive_orders()

            if not external_orders:
                _logger.info('%s (import orders): no more orders to import', self.name)
                break

            # Filter orders based on the integration settings
            filtered_external_orders = self.filter_received_orders(external_orders)
            filtered_external_orders_count += len(filtered_external_orders)

            for order_data in filtered_external_orders:
                # In fact this method returns not only newly created input files but also
                # existing input files that were already created before.
                new_input_file = self._create_input_file_from_received_data(order_data)
                new_input_files |= new_input_file

            # Update last receive datetime
            updated_at_list = [order_data['updated_at'] for order_data in external_orders]
            last_receive_dt = self._find_max_datetime(updated_at_list)

            if last_receive_dt is not None:
                self.last_receive_orders_datetime = last_receive_dt - timedelta(seconds=1)

            # Check if we have more orders to import
            if len(external_orders) < adapter.order_limit_value():
                break

        _logger.info(
            '%s (import orders): {count: %s, updated_at: %s, input_files: %s}',
            self.name,
            filtered_external_orders_count,
            last_receive_dt,
            new_input_files.ids,
        )

        return new_input_files

    @expose_for_testing('Import Order by ID')
    def integrationApiReceiveOrder(self):
        # TODO: Left for compatibility but should be removed in next release (after merging task)
        # related to test methods
        # Also, we shouldn't allow to run this method from test tab because it will be added to
        # import wizard
        if not self.test_method_parameter:
            return False

        return self.with_context(skip_create_order_from_input=True) \
            .fetch_order_by_id(self.test_method_parameter)

    @expose_for_testing('Import Product by ID')
    def integrationApiReceiveExternalProduct(self):
        if not self.test_method_parameter:
            return False

        external_product = self.import_external_product(self.test_method_parameter)
        return external_product

    @expose_for_testing('Calculate Quantity for Product')
    def integrationApiCalculateProductQty(self):
        if not self.test_method_parameter:
            return False

        locations = self.env['stock.location']
        location_ids_list = self.location_line_ids._group_by_external_code()

        for (external_location_id, internal_locations) in location_ids_list:
            if not self.allow_multi_company_inventory_calculation:
                # Use sudo() to safely read company_id even if access is restricted
                internal_locations = internal_locations.filtered(lambda loc: loc.sudo().company_id == self.company_id)
            locations |= internal_locations

        if not locations:
            raise UserError(_(
                'The inventory locations for "%s" are not specified.\n\n'
                'Please go to "E-Commerce Integrations → Stores → %s → Inventory tab" and specify '
                'the locations where inventory will be managed.'
            ) % (self.name, self.name))

        result_text = self._prepare_calculation_qty_with_bom(self.test_method_parameter, locations)
        return self.env['message.wizard'].create_and_run(result_text)

    def _prepare_calculation_qty_with_bom(self, product_id, locations):
        """
        1. Receives a product.product ID
        2. Calculates per-location producible quantities based on BOM
        3. Builds a clear, concise report
        4. Returns the assembled report text
        """
        try:
            product_id = int(product_id)
        except ValueError:
            raise UserError(_('Invalid product ID: %s') % product_id)

        product = self.env['product.product'].browse(product_id)
        if not product:
            raise UserError(_('No product found with ID %s.') % product_id)

        # Prepare basic info
        qty_field = self.synchronise_qty_field

        report = []
        line_text = '═' * 50

        report.append(_(
            '%s\n'
            'Calculating producible quantity for product variant:\n'
            '  • Product Name: %s (ID: %s)\n'
            '  • Product UOM: %s'
        ) % (line_text, product.display_name, product.id, product.uom_id.display_name))

        total_producible_qty = 0
        location_results = []
        skipped_locations = []

        for loc in locations:
            location = loc.sudo()
            company = location.company_id
            if not company:
                skipped_locations.append(location)
                _logger.warning('Location %s has no company or inaccessible', loc.id)
                continue

            context = {'location': location.id, 'company_id': company.id}

            # Create a new variable with the product in the context of the company
            product_company = product.with_company(company)

            bom = self.env['mrp.bom'].with_company(company)._bom_find(
                products=product_company,
                company_id=company.id,
                bom_type='normal'
            ).get(product_company)

            if not bom:
                available_product_qty = getattr(product_company.with_context(**context), qty_field)
                location_results.append({
                    'location_id': location.id,
                    'location_name': location.display_name,
                    'company_id': company.id if company else None,
                    'company_name': company.name if company else 'N/A',
                    'available_qty': available_product_qty,
                    'producible_qty': 0,
                    'sendable_qty': available_product_qty,
                })
                report.append(_(
                    'Product "%s" (ID: %s) has no manufacturing BOM '
                    'in company %s.\n'
                    'Quantity for this product: %s'
                ) % (product_company.display_name, product_company.id, company.name, available_product_qty))
                continue

            # Switch to the company context if multi-company mode is enabled
            bom = bom.with_company(company)
            report.append(_(
                '  • Using BOM: %s (ID: %s)\n'
                '  • BOM Qty: %s\n'
                '  • BOM UOM: %s\n'
            ) % (bom.display_name, bom.id, bom.product_qty, bom.product_uom_id.display_name))

            report.append(_(
                '📍 Processing Location: %s (ID: %s)'
            ) % (location.display_name, location.id))

            # We'll keep track of each component's “maximum possible batches”
            # and then find the minimum of these across all BOM lines.
            min_possible_batches_for_location = None

            __, bom_line_data = bom.explode(product_company, 1.0)

            for bom_line, line_data in bom_line_data:
                component = bom_line.product_id.with_company(company)
                component_uom = component.uom_id
                component_uom_name = component_uom.display_name

                required_qty = float(line_data.get('qty', 0.0) or 0.0)
                available_component_qty = float(getattr(component.with_context(**context), qty_field) or 0.0)

                bom_line_uom_name = bom_line.product_uom_id.display_name
                report.append(_(
                    '\t  • BOM Line:\n'
                    '\t  • Component Name: %s (ID: %s)\n'
                    '\t  • Component Qty: %s\n'
                    '\t  • Component UOM: %s\n'
                    '\t  • BOM Line Qty: %s\n'
                    '\t  • BOM Line UOM: %s'
                ) % (
                    component.display_name,
                    component.id,
                    available_component_qty,
                    component_uom_name,
                    required_qty,
                    bom_line_uom_name,
                ))

                # 1) Skip services and consu without BOM
                if component.type == 'service' or \
                        (component.type == 'consu' and not component.is_storable and not component.bom_ids):
                    report.append(_(
                        '\t\tComponent is a consumable or service. Excluded from production calculation.\n')
                    )
                    continue

                # 2) If component has its own BOM → recurse for producible qty
                if component.bom_ids and component.type in ['product', 'consu']:
                    visited = set()
                    producible_from_bom = component.with_context(**context)._compute_qty_producible(
                        qty_field, visited_products=visited,
                    )
                    # Add producible quantity from BOM to available quantity
                    available_component_qty += producible_from_bom
                    report.append(_(
                        '\t\tComponent has its own BOM.\n'
                        '\t  • Recursively computing producible qty for this component: %s'
                    ) % available_component_qty)
                else:
                    report.append(_(
                        '\t\tComponent has no BOM, using its own quantity: %s'
                    ) % available_component_qty)

                # 3) If required qty == 0 → does not constrain production (continue)
                if float_is_zero(required_qty, precision_digits=6):
                    report.append(_('\t\tRequired qty is zero → does not constrain production.\n'))
                    continue

                # 4) Zero-availability after skips and zero-required check (mirror base)
                is_available_zero = float_is_zero(available_component_qty, precision_rounding=component_uom.rounding)
                if is_available_zero or available_component_qty <= 0:
                    report.append(_(
                        '\t  • CRITICAL: %s has no available quantity.\n'
                        '\t  • Production is IMPOSSIBLE due to missing component.\n'
                    ) % component.display_name)
                    min_possible_batches_for_location = 0
                    break

                # 5) UoM conversion to BOM line UoM if different
                if bom_line.product_uom_id != component.uom_id:
                    original_available_component_qty = available_component_qty
                    available_component_qty = component.uom_id._compute_quantity(
                        available_component_qty, bom_line.product_uom_id,
                    )
                    report.append(_(
                        '\tComponent has a different UOM than the BOM line.\n'
                        '\t  • Converted UOM: %s → %s\n'
                        '\t  • Converted value: %s → %s'
                    ) % (
                        component_uom_name,
                        bom_line_uom_name,
                        original_available_component_qty,
                        available_component_qty
                    ))

                # 6) Integer batches, like in the base method
                possible_batches = available_component_qty // required_qty

                # Update our min_possible_batches across all lines
                if min_possible_batches_for_location is None:
                    min_possible_batches_for_location = possible_batches
                else:
                    min_possible_batches_for_location = min(min_possible_batches_for_location, possible_batches)

                report.append(_(
                    '\t  • Possible Batches for this component: %s\n'
                ) % possible_batches)

            # Turn min batches into produced quantity (mirror base)
            if min_possible_batches_for_location is None:
                produced_qty = 0.0
                report.append(_('\t  • WARNING: No constraining lines → produced qty = 0.\n'))
            else:
                produced_qty = min_possible_batches_for_location * bom.product_qty
                report.append(_(
                    'Minimum possible batches across all components: %s\n'
                    'Minimum possible batches %s * BOM Qty %s = %s\n'
                    'Produced quantity for current location: %s\n'
                ) % (
                    min_possible_batches_for_location,
                    min_possible_batches_for_location,
                    bom.product_qty,
                    produced_qty,
                    produced_qty,
                ))

            # Adjust UOM if necessary
            if produced_qty and product.uom_id != bom.product_uom_id:
                original_produced_qty = produced_qty
                produced_qty = bom.product_uom_id._compute_quantity(
                    produced_qty, product.uom_id
                )
                report.append(_(
                    'Product "%s" (ID: %s)'
                    ' has a different UOM than the BOM line.\n'
                    '  • Converted UOM: %s → %s\n'
                    '  • Converted value: %s → %s'
                ) % (
                    product_company.display_name,
                    product_company.id,
                    bom.product_uom_id.display_name,
                    product_company.uom_id.display_name,
                    original_produced_qty, produced_qty,
                ))

            available_product_qty = float(getattr(product_company.with_context(location=loc.id), qty_field) or 0.0)
            sendable_qty = available_product_qty + produced_qty
            total_producible_qty += produced_qty

            # Store results for this location
            location_results.append({
                'location_id': loc.id,
                'location_name': loc.display_name,
                'company_id': company.id if company else None,
                'company_name': company.name if company else 'N/A',
                'available_qty': available_product_qty,
                'producible_qty': produced_qty,
                'sendable_qty': sendable_qty,
            })

        # Header with totals
        report.insert(
            0,
            _(
                '📦 FINAL CALCULATION RESULT\n'
                '%s\n'
                ' • Total Producible Quantity: %.2f %s\n'
                ' • Multi-company mode: {"Enabled" if self.allow_multi_company_inventory_calculation else "Disabled"}\n'
                ' Result across all configured locations\n'
            ) % (line_text, total_producible_qty, product.uom_id.display_name)
        )

        # Add detailed location results to the report
        for result in reversed(location_results):
            report.insert(
                1,
                _(
                    '📍 Location: %s (ID: %s)\n'
                    '\t• Available Quantity: %.2f %s\n'
                    '\t• Producible Quantity: %.2f %s\n'
                    '\t• Sendable Quantity: %.2f %s\n'
                    '\t• Company: %s (ID: %s)\n'
                ) % (
                    result['location_name'],
                    result['location_id'],
                    result['available_qty'],
                    product.uom_id.display_name,
                    result['producible_qty'],
                    product.uom_id.display_name,
                    result['sendable_qty'],
                    product.uom_id.display_name,
                    result['company_name'],
                    result['company_id'],
                )
            )

        if skipped_locations:
            names = ', '.join(f'{location.display_name} (ID: {location.id})' for location in skipped_locations)
            report.append(_(
                '\n Skipped locations without company or inaccessible: %s'
            ) % names)

        return '\n'.join(report)

    def run_create_products_in_odoo_by_blocks(self, external_templates):
        return external_templates.run_import_products()

    @expose_for_testing('Create Products in Odoo (Using External Records)')
    def integrationApiCreateProductsInOdoo(self):
        block = 1
        limit = self.get_external_block_limit()
        external_templates = self.env['integration.product.template.external'].search([
            ('integration_id', '=', self.id),
        ])

        context = {
            'company_id': self.company_id.id,
            'job_integration_id': self.id,
            'job_integration_job_type': 'product',
        }
        self = self.with_context(**context)
        description_ = _('%s: Create Products In Odoo. Prepare Products For Creating [block %s]') % self.name

        while external_templates:
            _external_ids = external_templates[:limit]

            self.with_delay(
                priority=5,
                description=(description_ % block),
            ).run_create_products_in_odoo_by_blocks(_external_ids)

            block += 1
            external_templates = external_templates[limit:]

    @expose_for_testing('Run Product Catalog Validation Test')
    def integrationApiProductsValidationTest(self):
        validation_results = self._get_product_validation_report_html()

        # If there are validation errors, create wizard action
        if validation_results:
            message_wizard = self.env['message.wizard'].create({
                'message': 'Warning!',  # Hidden field
                'export_html': validation_results,
            })
            action = message_wizard.run_wizard('integration_message_wizard_validate_template_form')
            return action

        # Show message if no errors found
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Products Validation'),
                'message': 'No errors found. You can proceed with the import.',
                'type': 'success',
                'sticky': False,
            }
        }

    def run_import_customers_by_blocks(self, external_customer_ids):
        self.ensure_one()

        context = {
            'company_id': self.company_id.id,
            'job_integration_id': self.id,
            'job_integration_job_type': 'customer',
        }

        result = []
        for customer_id in external_customer_ids:
            job_kwargs = self._job_kwargs_import_single_customer(customer_id)
            job = self.with_context(**context).with_delay(**job_kwargs).import_single_customer(customer_id)

            result.append(job)

        return result

    def import_single_customer(self, external_customer_id):
        """
        Import a single customer along with their addresses.
        Args:
            external_customer_id (str): External ID of the customer.
        Returns:
            List: Imported partners (customer and their addresses).
        """
        adapter = self.adapter

        customer, addresses = adapter.get_customer_and_addresses(external_customer_id)

        if not customer:
            raise UserError(
                _(
                    'Customer with ID "%s" not found in external system. Please verify the customer ID and try again.'
                ) % external_customer_id
            )

        # Ensure 'invoice' type addresses come first, then others (type is None).
        # This guarantees that the main billing address is processed first and linked as primary.
        billing_addresses = (
            [a for a in addresses if a.get('type') == 'invoice'] +  # NOQA
            [a for a in addresses if a.get('type') is None]
        )
        shipping_addresses = list(filter(lambda x: x.get('type') == 'delivery', addresses))

        imported_contacts = self.env['res.partner']

        # Always guarantee a factory call
        billing_list = billing_addresses or [None]

        # Process billing + shipping pairs
        for i, billing_address in enumerate(billing_list):
            shipping_address = shipping_addresses[i] if i < len(shipping_addresses) else None

            PartnerFactory = self.env['integration.res.partner.factory'].create_factory(
                self.id,
                customer_data=customer,
                billing_data=billing_address,
                shipping_data=shipping_address,
                is_initial_import=True,
            )

            partner, addresses = PartnerFactory.get_partner_and_addresses()

            imported_contacts |= partner
            imported_contacts |= addresses['billing']
            imported_contacts |= addresses['shipping']

        return imported_contacts

    def _import_external_tax(self, tax_id):
        adapter_external_data = self.adapter.get_single_tax(tax_id)

        if not adapter_external_data:
            return None

        external_record = self._import_external_record(
            self.env['integration.account.tax.external'],
            adapter_external_data,
        )
        mapping = external_record.create_or_update_mapping()

        return mapping._fix_unmapped_tax_one(external_data=adapter_external_data)

    def _fetch_external_carrier(self, carrier_data):
        return carrier_data

    def _import_external_carrier(self, carrier_data):
        adapter_external_data = self._fetch_external_carrier(carrier_data)

        external_record = self._import_external_record(
            self.env['integration.delivery.carrier.external'],
            adapter_external_data,
        )
        mapping = external_record.create_or_update_mapping()

        return mapping._fix_unmapped_shipping_one()

    def import_external_product(self, template_ids):
        """
        (1) receive actual product data
        (2) create or update externals/mappings
        (3) try to map external records (integration.product.template.mapping)

        Returns:
            str: Formatted message string with detailed import results
        """

        external_templates, external_variants, \
            error_list, failed_external_template_ids = self._import_external_product(template_ids)

        message = ''
        total_processed = len(template_ids) if isinstance(template_ids, list) else 1
        successful_imports = len(external_templates) + len(external_variants)

        is_all_imports_failed = total_processed == len(failed_external_template_ids)

        # Header with summary
        message += _('Summary:\n')
        message += _('• Total templates processed: %s\n') % total_processed
        message += _('• Successful imports: %s\n') % successful_imports
        message += _('• Failed imports: %s\n\n') % len(error_list)

        if not external_templates and not external_variants:
            message += _('❌ No external products found or imported\n')
            if error_list:
                message += _('\nErrors encountered:\n')
                for error in error_list:
                    message += _('\t• %s\n\n') % error
            raise UserError(_('\n\n%s') % message)

        # Success section
        # Prevent display if there are only problematic products
        if not is_all_imports_failed:
            message += _('✅ Import%s completed successfully!\n\n') % (
                ' (partial)' if failed_external_template_ids else ''
            )

            if external_templates:
                # Filter out deleted records before accessing fields
                existing_templates = external_templates.exists()
                total_templates = len(existing_templates)
                shown_templates = existing_templates[:20]
                remaining_templates = total_templates - 20

                message += _('📦 Imported Templates (%s total):\n') % total_templates
                for template in shown_templates:
                    message += _('  • %s (ID: %s, SKU: %s)\n') % (
                        template.name,
                        template.code,
                        template.external_reference or 'N/A'
                    )

                if remaining_templates > 0:
                    message += _('  ... and %s more templates\n') % remaining_templates
                message += '\n'

            if external_variants:
                # Filter out deleted records before accessing fields
                existing_variants = external_variants.exists()
                total_variants = len(existing_variants)
                shown_variants = existing_variants[:20]
                remaining_variants = total_variants - 20

                message += _('🔧 Imported Variants (%s total):\n') % total_variants
                for variant in shown_variants:
                    message += _('  • %s (ID: %s, SKU: %s)\n') % (
                        variant.name,
                        variant.code,
                        variant.external_reference or 'N/A'
                    )

                if remaining_variants > 0:
                    message += _('  ... and %s more variants\n') % remaining_variants
                message += '\n'

        if is_all_imports_failed:
            total_errors = len(error_list)
            # Errors section (also limit to first 20)
            shown_errors = error_list[:20]
            remaining_errors = total_errors - 20

            message = '\n\n'
            message += _('⚠️ ERRORS (%s total):\n\n') % total_errors
            for error in shown_errors:
                message += _('\t• %s\n\n') % (error)

            if remaining_errors > 0:
                message += _('  ... and %s more errors\n') % remaining_errors
            message += '\n'

            raise UserError(_('\n\n%s') % message)

        elif failed_external_template_ids:
            message += _(
                '⚠️ Errors when importing products:\n%s.\n'
            ) % ',\n'.join(failed_external_template_ids)
            message += self._import_external_product_separate_job(failed_external_template_ids) or ''

        return message

    def _import_external_product_separate_job(
        self,
        failed_external_template_ids: list[str] = None,
    ):
        """
        Moving failed imports in separate job to isolate them and make retry only for failed imports possible.
        It works only if current method is called from a job, if not -- it will be ignored.
        :param failed_external_template_ids: List of failed external template IDs.
        """
        job_uuid = self.env.context.get('job_uuid')
        if not job_uuid:
            return

        job_record = self.env['queue.job'].sudo().search([('uuid', '=', job_uuid)], limit=1)
        if not job_record:
            return

        job = self.with_context(
            company_id=job_record.company_id.id,
            job_integration_id=self.id,
            job_integration_job_type='product',
        ).with_delay(
            priority=2,
            description=job_record.name + ' [Retry]',
        ).import_external_product(failed_external_template_ids)

        new_job = job.db_record() if isinstance(job, Job) else job
        new_job.parent_id = job_record

        return _(
            '\nAll failed imports are moved in separate job to isolate.\n'
            'See next failed job logs to see the details.'
        )

    def _import_external_product(self, template_ids, try_to_map=True):
        """
        Import external product templates and their variants.

        :param template_ids: List or single external template ID(s). Will be converted to strings.
        :return: Tuple of (external_templates, external_variants, errors, failed_external_template_ids):
            - external_templates: recordset of imported template records
            - external_variants: recordset of imported variant records
            - errors: list of error messages (empty if no errors)
            - failed_external_template_ids: list of failed external template IDs (empty if none failed)
        """
        if not isinstance(template_ids, list):
            template_ids = [template_ids]

        template_ids = [str(x) for x in template_ids]

        ExternalTemplate = self.env['integration.product.template.external']
        ExternalVariant = self.env['integration.product.product.external']

        external_templates = ExternalTemplate.browse()
        external_variants = ExternalVariant.browse()

        ext_templates_data, failed_external_template_ids, errors = self.adapter.get_product_templates(
            template_ids,
            raise_error=False,
        )

        if not ext_templates_data:
            return external_templates, external_variants, errors, failed_external_template_ids

        for template_data in ext_templates_data.values():
            template_id = template_data.get('id', 'unknown')
            external_template = None
            template_variants = ExternalVariant.browse()

            # - Savepoint isolates each template: failure of one doesn't rollback others.
            # - Outer try/except catches fatal errors (IntegrityError, ValidationError, etc.)
            #   and allows the loop to continue. Savepoint auto-rollbacks on exception exit.
            # - Inner try/except handles non-critical auto-mapping errors.
            #   Without inner try, mapping errors would bubble up and rollback the savepoint.
            try:
                with self.env.cr.savepoint():
                    external_template = self._import_external_record(ExternalTemplate, template_data)

                    if not external_template:
                        failed_external_template_ids.append(template_id)
                        errors.append(_('Failed to import external template: %s') % template_id)
                        continue

                    external_template.create_or_update_mapping()

                    # Import variants
                    variants_data = template_data.get('variants', [])
                    for variant_data in variants_data:
                        external_variant = self._import_external_record(ExternalVariant, variant_data)
                        if external_variant:
                            external_variant.create_or_update_mapping()
                            template_variants |= external_variant

                    # Create default variant if no variants exist
                    if not variants_data:
                        default_external_variant = external_template._create_default_external_variant()
                        default_external_variant.create_or_update_mapping()
                        template_variants |= default_external_variant

                    if try_to_map:
                        # Try auto-mapping (non-critical, errors are collected)
                        try:
                            external_template.try_map_template_and_variants(template_data)
                        except (es.ApiImportError, es.NotMappedToExternal, es.NotMappedFromExternal) as e:
                            error_message = _('Errors when trying to auto-match products:\n%s') % str(e)
                            errors.append(error_message)
                            failed_external_template_ids.append(template_id)

                # After successful savepoint: add to results
                if external_template and external_template.exists():
                    external_templates |= external_template
                    external_variants |= template_variants

            except (IntegrityError, AssertionError, UserError, ValidationError, NoExternal) as e:
                errors.append(str(e))
                failed_external_template_ids.append(template_id)

        return external_templates, external_variants, errors, list(set(failed_external_template_ids))

    def _import_external_record(self, external_model, external_data):
        name = external_data.get('name')

        # Get translation if name contains different languages
        if isinstance(name, dict) and name.get('language'):
            original = external_model.get_original_name(name, self)

            if original:
                name = original

        if not name:
            name = external_data['id']

        if not external_model._pre_import_external_check(external_data, self):
            return external_model

        result = external_model.create_or_update({
            'integration_id': self.id,
            'code': external_data['id'],
            'name': name,
            'external_reference': external_data.get('external_reference'),
        })
        result._post_import_external_one(external_data)

        return result

    def _import_external(self, model, method, external_data=None, remove_existing_records=False):
        if not external_data:
            external_data = getattr(self.adapter, method)()

        external_records = self.env[model]

        # Remove existing records if requested
        if remove_existing_records:
            existing_records = external_records.search([('integration_id', '=', self.id)])
            if existing_records:
                existing_records.unlink()

        for data in external_data:
            external_records |= self._import_external_record(external_records, data)

        external_records._post_import_external_multi(external_data)
        return external_records, external_data

    def export_template(self, template: 'models.Model', export_images=False, make_validation=False, force=False):
        """
        Be careful, this method have to be private because of there are many external validations
        before its calling. Urgently recommend use the `template.trigger_export(*args, **kw)`
        """
        self.ensure_one()
        template.ensure_one()
        assert template.exists(), _(
            'Product Template with Id = %s doesn\'t exist or has been deleted' % template.id
        )

        _logger.info(
            '%s: Integration `export_template` started with params: %s, %s, %s, %s',
            self.name,
            template,
            f'export_images={export_images}',
            f'make_validation={make_validation}',
            f'force={force}',
        )

        # Determine the `force_export` flag
        force_export = force or not template.get_external_code(self.id)

        context = {
            'company_id': self.company_id.id,
            'job_integration_id': self.id,
            'job_integration_job_type': 'product',
            'job_template_id': template.id,
        }

        self = self.with_context(**context)

        template = template.with_context(
            lang=self.get_integration_lang_code(),
            default_integration_id=self.id,
            integration_force_product_export=force_export,
        )

        if make_validation:
            template.validate_in_odoo(self, raise_error=True)

        template_data = template.to_export_format(self)
        # Now let's validate template in external system
        # In case we will be returned with external records to delete
        # we need to clean up and trigger export job again
        adapter = self.adapter
        ext_records_to_delete = adapter.validate_template(template_data)

        if ext_records_to_delete:
            # Unlink found incorrect external records (external mappings)
            for record in ext_records_to_delete:
                odoo_external_id = record.get('odoo_external_id')

                if odoo_external_id:
                    model_name = record['model']
                    external_record = self.env[f'integration.{model_name}.external'].browse(odoo_external_id)

                    external_record.unlink()

            # Trigger export again and finish current task
            job_kwargs = self._job_kwargs_export_template(template, export_images, force=force)

            self.with_delay(**job_kwargs).export_template(
                template,
                export_images=export_images,
                make_validation=make_validation,
                force=force,
            )

            return _('Some products didn\'t exists in external system. '
                     'External records where cleaned up and export was triggered again ')

        # Now let's check if such product already exist in external system
        # so instead of creating new we can import existing one
        if not template_data['external_id'] and template_data['products']:
            existing_external_product_id = adapter.find_existing_template(template_data)

            if existing_external_product_id:
                external_record = self.env['integration.product.template.external'].create_or_update({
                    'integration_id': self.id,
                    'code': existing_external_product_id,
                })
                external_record.create_or_update_mapping(odoo_id=template.id)

                job_kwargs = self._job_kwargs_import_product(external_record.code, external_record.name)
                self.with_delay(**job_kwargs).import_product(external_record.id)

                return _(
                    'Existing Product found in external system with id %s. Triggering job to '
                    'import product instead of exporting it.'
                ) % existing_external_product_id

        # 0. START EXPORT
        results_list = []
        t_mapping, *v_mapping_list = adapter.export_template(template_data)

        external_template = self._handle_mapping_data(template.id, t_mapping, v_mapping_list)

        results_list.append(
            _('SUCCESS! Product Template "%s" was exported successfully. Product Template Code in '
              'external system is "%s"') % (template.name, external_template.code)
        )

        # 1. Pricelists export.
        # Note: Always check the `pricelist_integration` property
        if self.pricelist_integration and force_export:
            # Do it in separate job in order to avoid rollback.
            job_kwargs = self._job_kwargs_export_specific_prices_template(template)
            self.with_delay(**job_kwargs).export_pricelists_one(template)

            results_list.append(LOG_SEPARATOR)
            results_list.append(_('Export Pricelists job was created.'))

        # 2. Images export.
        # Note: Always check the `allow_export_images` property
        if self.allow_export_images and (export_images or force_export):
            # Do it in separate job in order to avoid rollback.
            job_kwargs = self._job_kwargs_export_images(template)
            self.with_delay(**job_kwargs).export_template_images_verbose(template.id)

            results_list.append(LOG_SEPARATOR)
            results_list.append(_('Export Images job was created.'))

        # 3. Inventory export.
        if self.is_real_time_inventory_export_enabled and force_export:

            # Check if inventory export is required
            results_list.append(LOG_SEPARATOR)

            if self._should_export_inventory(template):
                # Export inventory in a separate job to avoid rollback in case of transaction errors
                template._export_inventory_on_template(self.id)
                results_list.append(_('Export Inventory job was created.'))
            else:
                results_list.append(
                    _('Inventory export was skipped because the product is not a product or a consumable with a BOM.')
                )

        # Update timestamp export for the external record
        external_record = template.to_external_record(self)
        external_record.update_timestamp_export()

        template.with_context(
            clean_context(template.env.context)
        ).export_template_hook(self.id, force_export)

        # Joining all results, so they will be visible in Job results log
        return '\n\n'.join(results_list)

    def _should_export_inventory(self, template):
        # Determine if the template qualifies for inventory export:
        #   1) Always respect exclusion flags
        #   2) Storable consumables (is_consumable_storable) - always allowed
        #   3) Consumables with BOMs - only if update_stock_for_manufacture_boms is enabled

        # Check exclusion flags first
        if template.exclude_from_synchronization or template.exclude_from_synchronization_stock:
            return False

        # Always allow storable consumables
        if template.is_consumable_storable:
            return True

        # For consumables with BOMs, check if this integration allows it
        if template.type == 'consu' and bool(template.bom_ids):
            return self.update_stock_for_manufacture_boms

        return False

    def _handle_mapping_data(self, template_id: int, t_mapping: dict, v_mapping_list: list) -> tuple:
        # 1. Handle template
        assert t_mapping['model'] == 'product.template', _('Expected product template mapping.')

        is_only_template = (
            len(v_mapping_list) == 1 and v_mapping_list[0]['external_id'].endswith('-0')
        )
        ref_field = self.product_reference_name
        ext_reference = t_mapping.get('external_reference')
        template = self.env['product.template'].browse(template_id)

        if not ext_reference and is_only_template:
            ext_reference = getattr(template, ref_field)

        template_vals = dict(
            name=template.name,
            code=t_mapping['external_id'],
            external_reference=ext_reference,
        )

        odoo_external_template_id = t_mapping['odoo_external_id']

        if odoo_external_template_id:
            external_template = self.env['integration.product.template.external'].browse(odoo_external_template_id)
            external_template.write(template_vals)
        else:
            external_template = self.env['integration.product.template.external'].create({
                'integration_id': self.id,
                **template_vals,
            })

        external_template.create_or_update_mapping(odoo_id=t_mapping['id'])

        # 2. Handle variants
        external_variants = self.env['integration.product.product.external']
        for v_mapping in v_mapping_list:
            odoo_id = v_mapping['id']
            variant = self.env['product.product'].browse(odoo_id)

            variant_vals = dict(
                name=variant.name,
                code=v_mapping['external_id'],
                external_reference=v_mapping.get('external_reference') or getattr(variant, ref_field),
            )

            odoo_external_variant_id = v_mapping['odoo_external_id']

            if odoo_external_variant_id:
                external_variant = self.env['integration.product.product.external'].browse(odoo_external_variant_id)
                external_variant.write(variant_vals)
            else:
                external_variant = external_template.external_product_variant_ids.filtered(
                    lambda x: x.code == v_mapping['external_id']
                )
                if external_variant:
                    external_variant.write(variant_vals)

            if not external_variant:
                external_variant = self.env['integration.product.product.external'].create({
                    'integration_id': self.id,
                    **variant_vals,
                })

            external_variant.create_or_update_mapping(odoo_id=odoo_id)
            external_variants |= external_variant

        external_template.external_product_variant_ids = [(6, 0, external_variants.ids)]

        return external_template

    def init_send_field_converter(self, *ar, **kw):
        raise NotImplementedError

    def export_pricelist_items_to_external_cron(self):
        _logger.info('Call Integration cron: Send Pricelist Items')

        integration_ids = self.search([
            ('state', '=', 'active'),
            ('pricelist_integration', '=', True),
        ])

        result = list()
        for integration in integration_ids:
            context = {
                'company_id': integration.company_id.id,
                'job_integration_id': integration.id,
                'job_integration_job_type': 'pricelist',
            }
            job = integration \
                .with_context(**context) \
                .with_delay(
                    description=f'{integration.name}: Export Pricelist Items Cron',
                ).export_pricelist_items_to_external()

            result.append(job)

        return result

    def export_pricelist_items_to_external(self):
        self.ensure_one()
        mapping_ids = self.env['integration.product.pricelist.mapping'].search([
            ('pricelist_id', '!=', False),
            ('integration_id', '=', self.id),
            ('integration_id.state', '=', 'active'),
        ])
        pricelist_ids = mapping_ids.mapped('pricelist_id')

        if not pricelist_ids:
            return pricelist_ids._integration_not_mapped_error()

        return pricelist_ids.trigger_update_items_to_external(integration_id=self.id)

    def cron_calculation_and_export_prices(self):
        """
        Cron entry point: launches full price sync (calculation + export) for active integrations.
        """
        raise NotImplementedError

    def search_templates_for_specific_prices(self, pricelist_ids=None, item_ids=None):
        # TODO: use `pricelist_ids`` or 'item_ids' to do search more accurately
        mapping_ids = self.env['integration.product.template.mapping'].search([
            ('integration_id', '=', self.id),
            ('template_id.active', '=', True),
        ])
        return mapping_ids.mapped('template_id')

    def export_pricelists_multi(self, pricelist_ids=None, item_ids=None, updating=False):
        block_number = 1
        block_list = list()
        message_list = list()

        context = {
            'company_id': self.company_id.id,
            'job_integration_id': self.id,
            'job_integration_job_type': 'pricelist',
        }
        self = self.with_context(**context)

        template_ids = self.search_templates_for_specific_prices(
            pricelist_ids=pricelist_ids,
            item_ids=item_ids,
        )
        _template_ids = template_ids.browse().with_context(default_integration_id=self.id)
        _invalid_template_ids = _template_ids.browse()

        for template in template_ids:
            if not template.to_external_record(self, raise_error=False):  # TODO
                message_list.append('%s was skipped due to not fully mapped.' % template)
                continue

            if not all(
                variant.to_external_record(self, raise_error=False)
                for variant in template.prepare_integration_variants(self.id)
            ):
                message_list.append('%s was skipped due to their variants not fully mapped.' % template)
                continue

            price_data = template.convert_pricelists(
                self.id,
                pricelist_ids=pricelist_ids,
                item_ids=item_ids,
            )

            if price_data:
                if self._validate_pricelist_data(price_data):
                    _template_ids |= template
                    block_list.append(price_data)
                else:
                    _invalid_template_ids |= template

            if len(block_list) >= (EXPORT_EXTERNAL_BLOCK / 10):
                job_kwargs = self._job_kwargs_export_specific_prices_data(block_number)
                job = self.with_delay(**job_kwargs)._export_pricelist_data(block_list, updating)
                message_list.append(
                    _('Pricelists Batch (%s) was created: %s') % (block_number, job)
                )

                block_number += 1
                block_list = list()
                _template_ids = _template_ids.browse()

        if block_list:
            job_kwargs = self._job_kwargs_export_specific_prices_data(block_number)
            job = self.with_delay(**job_kwargs)._export_pricelist_data(block_list, updating)
            message_list.append(
                _('Pricelists Batch (%s) was created: %s') % (block_number, job)
            )

        for i_tmpl in _invalid_template_ids:
            job_kwargs = self._job_kwargs_export_specific_prices_template(i_tmpl)
            job = self.with_delay(**job_kwargs).export_pricelists_one(i_tmpl)
            message_list.append(
                _('Pricelist items for %s have errors. Separate job was released.') % i_tmpl
            )

        return '\n'.join(message_list) or _('Skipped. Pricelist items for export not found.')

    def export_pricelists_one(self, template):
        data = template.convert_pricelists(self.id, raise_error=True)

        if not data:
            message = _(
                '%s: there are no any specific prices for product template "%s"'
                % (self.name, template.display_name)
            )
            return message

        result = self._export_pricelist_data(data)
        return result

    def _export_pricelist_data(self, data, updating=False):
        """
        :return:

            [('product.template(145,) / 52: []', ['product.product(167,) / 52-0: [(12, 106)]'])]

                product.product(167,):  odoo product variant
                52-0: odoo product variant external code
                12: odoo pricelist item id
                106: external pricelist item id
        """
        if not isinstance(data, list):
            data = [data]

        adapter = self.adapter
        result, sub_result, tmpl_ids = [], [], []

        for x_data in self._generate_pricelist_data(data):
            res = adapter.export_pricelists(x_data, updating)
            sub_result.append(res)

        for t_data_cls, v_data_cls_list in sub_result:
            tmpl_ids.append(t_data_cls.tmpl_id)

            t_dump = t_data_cls.dump()
            v_dump = [x.dump() for x in v_data_cls_list]
            result.append((t_dump, v_dump))

        if tmpl_ids:
            self.env['product.template']._unmark_force_sync_pricelist(tmpl_ids)

        return result

    def _generate_pricelist_data(self, data):
        for t_tuple, v_tuple_list in data:
            t_tuple_init = PriceList.from_tuple(t_tuple, self)
            v_tuple_list_init = [PriceList.from_tuple(x, self) for x in v_tuple_list]
            yield t_tuple_init, v_tuple_list_init

    @staticmethod
    def _validate_pricelist_data(price_data):
        """
        (
            (591, 'product.template', '64', [...], True),
            [
                (632, 'product.product', '64-168', [...], True),
                (636, 'product.product', '64-169', [...], True),
                (633, 'product.product', '64-170', [...], True),
            ]
        )
        """
        template, variants = price_data
        prices = sum([x[3] for x in variants], template[3])
        is_valid = all(x['_is_valid'] for x in prices)
        return is_valid

    def export_template_images_verbose(self, template_id: int, erase_mappings=False):
        template = self.env['product.template'].browse(template_id)

        try:
            # Attempt to export images
            result = self.export_template_images(template.id, erase_mappings=erase_mappings)
        except Exception:
            # Log the full traceback for debugging
            buff = StringIO()
            traceback.print_exc(file=buff)
            _logger.error(buff.getvalue())

            # Provide detailed error feedback to the user
            message = _(
                'Failed to export images for product template "%s".\n\n'
                'An unexpected error occurred during the export process.\n'
                'Please review the error details below or contact support (https://support.ventor.tech/) '
                'for assistance.\n\n'
                'Detailed Traceback:\n%s'
            ) % (template.name, buff.getvalue())
            raise es.ApiExportError(message)

        # Handle cases where there is nothing to export
        if result is None:
            message = _(
                'There are no images to export for product template "%s".\n\n'
                'Please ensure that the product template has images available for export.\n\n'
                'If the issue persists, contact support: https://support.ventor.tech/'
            ) % template.name
            return message

        # Handle failure to export images
        if result is False:
            message = _(
                'Failed to export images for product template "%s".\n\n'
                'This may be caused by broken or missing image files or incorrect configuration. '
                'Please verify the product template and try again.\n\n'
                'If the issue persists, contact support: https://support.ventor.tech/'
            ) % template.name
            raise es.ApiExportError(message)

        # Successful export
        message = _(
            'Images for product template "%s" were exported successfully:\n\n%s'
        ) % (template.name, result)
        return message

    def export_template_images(self, template_id: int, erase_mappings=False) -> List[Dict]:
        self.ensure_one()

        template = self.env['product.template'].browse(template_id)
        external_template = template.to_external_record(self)

        if erase_mappings:
            external_template.all_image_external_ids.unlink()

        datacls_list = template.with_context(
            lang=self.get_integration_lang_code(),
        ).to_images_export_format(self)

        return external_template._sync_images_data_out(datacls_list)

    def export_tracking(self, pickings):
        self.ensure_one()

        order = pickings.mapped('sale_id')
        assert len(order) == 1

        sale_order_id = order.to_external(self)
        tracking_data = pickings.to_export_format_multi(self)

        adapter = self.adapter
        result = adapter.export_tracking(sale_order_id, tracking_data, force_done=self.force_full_fulfillment)

        if result:
            pickings.mark_integration_sent()

        return result

    def send_picking(self, picking):
        self.ensure_one()

        order = picking.sale_id
        sale_order_id = order.to_external(self)
        picking_data = picking.to_export_format(self)

        if not picking_data:
            raise ValidationError(_(
                'Sending was skipped because not all transfers are validated yet.\n\n'
                'Please ensure all other related transfers are validated before attempting to send this picking.'
            ))

        result = self.adapter.send_picking(sale_order_id, picking_data)

        if result:
            picking.mark_integration_sent()

        # The rest of logic can be applied only for Shopify and Magento 2 integrations
        # For other integrations, result will be empty list
        if result:
            for rec in result:
                rec['internal_status'] = 'done'

            picking.sale_id._apply_values_from_external({'order_fulfillments': result})

        return result

    def export_sale_order_status(self, order):
        self.ensure_one()

        external_order_id = order.to_external(self)
        vals = order._prepare_vals_for_sale_order_status()

        return self.adapter.send_sale_order_status(external_order_id, vals)

    def export_attribute(self, attribute: 'models.Model'):
        self.ensure_one()
        adapter = self.adapter

        to_export = attribute.to_export_format(self)
        code = adapter.export_attribute(to_export)

        attribute.create_mapping(self, code, extra_vals={'name': attribute.name})

        return code

    def export_attribute_value(self, attribute_value: 'models.Model'):
        self.ensure_one()
        adapter = self.adapter

        external_attribute = attribute_value.attribute_id.to_external_record_or_export(self)

        attribute_value_data = attribute_value.to_export_format(self)
        attribute_value_code = adapter.export_attribute_value(attribute_value_data)

        mapping = attribute_value.create_mapping(
            self,
            attribute_value_code,
            extra_vals={
                'name': attribute_value.name,
            },
        )

        mapping.external_attribute_value_id.external_attribute_id = external_attribute.id  # TODO: Bad pattern

        return attribute_value_code

    def export_category(self, category: 'models.Model'):
        self.ensure_one()
        adapter = self.adapter

        code = adapter.export_category(category.to_export_format(self))
        category.create_mapping(self, code, extra_vals={'name': category.name})

        return code

    def export_inventory_for_variant_with_delay(self, variant: 'models.Model'):
        variant.ensure_one()
        name = variant.display_name

        try:
            # Attempt to export the inventory for the variant
            result = self.export_inventory(variant, cron_operation=False)
        except Exception:
            buff = StringIO()
            traceback.print_exc(file=buff)
            _logger.error(buff.getvalue())

            # Provide detailed feedback to the user on the failure
            message = _(
                'Failed to export stock quantities for product variant "%s".\n\n'
                'An unexpected error occurred during the export process. Please review the details below '
                'or contact support for assistance.\n\n'
                'Detailed Traceback:\n%s'
            ) % (name, traceback.format_exc())
            raise es.ApiExportError(message)

        # If no result, inform the user that there's nothing to export
        if not result:
            message = _(
                'There are no stock quantities to export for product variant "%s".\n\n'
                'Ensure that the variant has stock quantities to export before trying again.'
            ) % name
            return message

        # Handle the result of the export
        __, export_success, err_msg = result[0]

        if not export_success:  # TODO: result may be a list of booleans (Presta case)
            # If export fails, use the error message or a default one
            message = err_msg or _('Failed to export inventory for Product Variant "%s".') % name
            raise es.ApiExportError(message)

        # Success message with details
        message = _(
            'Stock quantities for product variant "%s" were exported successfully:\n\n%s'
        ) % (name, export_success)
        return message

    def _get_skipped_variants_for_inventory(self, variants: 'models.Model'):
        company_ids = (self.company_id.id, False)
        skipped_variant_ids = variants.filtered(
            lambda x: self not in x.integration_ids or not (x.company_id.id in company_ids)
        )
        return skipped_variant_ids

    def export_inventory(self, variants: 'models.model', cron_operation=True):
        # 1. Filter unsuitable records
        skipped_variants = self._get_skipped_variants_for_inventory(variants)

        if skipped_variants:
            _logger.info(
                '%s export inventory: filtered product variants: %s',
                self.name,
                skipped_variants.ids,
            )

        # 2. Prepare export data
        to_export_variant_ids = variants - skipped_variants
        inventory_data, failed_variants = self._collect_inventory_data(
            to_export_variant_ids,
            raise_error=(not cron_operation),
        )

        if failed_variants:
            _logger.info(
                '%s export inventory: skipped product variants: %s',
                self.name,
                failed_variants.ids,
            )

        # 3. Create separate `obviously failed` jobs for unmapped records
        if cron_operation and failed_variants:
            # According to `VSOPC-421` no need to do something with that
            pass

        if not inventory_data:
            return None

        # 4. Export
        result = self.adapter.export_inventory(inventory_data)

        # 5. Validate result
        if cron_operation:
            self._validate_export_inventory_result(result)

        return result

    def _collect_inventory_data(self, variants: 'models.Model', raise_error: bool):
        self.ensure_one()

        # Check if inventory locations are specified
        lines = self.location_line_ids
        if not lines:
            raise UserError(_(
                'The inventory locations for "%s" are not specified.\n\n'
                'Please go to "E-Commerce Integrations → Stores → %s → Inventory tab" and specify '
                'the locations where inventory will be managed.'
            ) % (self.name, self.name))

        inventory_data = dict()
        fail_variant_ids = self.env['product.product']
        location_ids_list = lines._group_by_external_code()

        # Check if advanced inventory is enabled and if multi-source is properly set up
        if self.advanced_inventory():
            if not all(x[0] for x in location_ids_list):
                raise UserError(_(
                    '%s: Multi-source inventory is not properly configured.\n\n'
                    'Please ensure that all external locations are set up correctly '
                    'in "E-Commerce Integrations → Stores → %s → Inventory tab".'
                ) % (self.name, self.name))
        else:
            if len(location_ids_list) > 1:
                raise UserError(_(
                    '%s: Multi-source inventory is not allowed or is not properly configured.\n\n'
                    'Please review the "E-Commerce Integrations → Stores → %s → Inventory tab" and ensure '
                    'that multi-source inventory is either disabled or set up correctly.'
                ) % (self.name, self.name))

        # invalidate cache for all product's qty_fields
        # it seems that odoo doesn't recompute qty_fields.
        # if we read qty_fields, then change it, then read again.
        # doesn't seem to be a real case
        # (usually export_inventory is done in single transaction).
        # added to fix test, but I don't think that it affects performance very much.
        variants.invalidate_recordset([self.synchronise_qty_field])

        for product in variants:
            external_record = product.to_external_record(self, raise_error=raise_error)
            if not external_record:
                fail_variant_ids |= product
                continue

            data_list = list()
            for (external_location_id, locations) in location_ids_list:
                data = self._prepare_inventory_data(product, locations, external_record, external_location_id)
                data_list.append(data)
            inventory_data[external_record.code] = data_list

        return inventory_data, fail_variant_ids

    def _validate_export_inventory_result(self, result_list):
        Variant = self.env['product.product']
        failed_variant_ids = Variant.browse()

        for external_id, result, err_msg in result_list:
            if not result:
                failed_variant_ids |= Variant.from_external(self, external_id)
            if err_msg:
                _logger.error(err_msg)

        if failed_variant_ids:
            self._create_separate_inventory_export_job(failed_variant_ids)
        return failed_variant_ids

    def _create_separate_inventory_export_job(self, variant_ids):
        _logger.warning(
            'Integration "%s": separate export inventory jobs for: %s', self.name, variant_ids,
        )
        # Create separate export jobs (isolated transactions) which will be highly likely
        # failed in order to notify user for existing troubles
        result = []
        context = {
            'company_id': self.company_id.id,
            'job_integration_id': self.id,
            'job_integration_job_type': 'inventory',
        }
        self = self.with_context(**context)
        variant_ids = variant_ids.with_context(default_integration_id=self.id)

        for variant in variant_ids:
            job_kwargs = self._job_kwargs_export_inventory_variant(variant)
            job = self \
                .with_delay(**job_kwargs) \
                .export_inventory_for_variant_with_delay(variant)

            result.append(job)

        return result

    def _search_pricelist_mappings(self):
        pricelist_map_ids = self.env['integration.product.pricelist.mapping'].search([
            ('integration_id', '=', self.id),
        ])
        return pricelist_map_ids.mapped('pricelist_id').ids

    def _get_wh_from_external_location(self, external_location_code: str):
        record = self.location_line_ids.filtered(  # TODO: what if there will be a recordset
            lambda x: x.external_location_id.code == external_location_code,
        )
        return record[:1].warehouse_id

    def _build_adapter_core(self):
        settings = self.to_dictionary()

        klass = self.get_class()
        adapter_core = klass(settings)

        adapter_core._integration_id = self.id
        adapter_core._integration_name = self.name
        adapter_core._adapter_hash = self.get_hash(settings)

        return adapter_core

    def _build_adapter(self):
        self.write_settings_fields()
        adapter_core = self._adapter_hub_.get_core(self)
        return Adapter(adapter_core, self.env)

    def to_dictionary(self):
        self.ensure_one()
        return {
            'name': self.name,
            'type_api': self.type_api,
            'fields': self.field_ids.to_dictionary(),
            'data_block_size': int(
                self.env['ir.config_parameter'].sudo().get_param('integration.import_data_block_size')
            ),
        }

    def filter_received_orders(self, external_orders_data_list: list):
        """
        Global method to filter received orders.
        This method will call specific filtering methods based on the integration type.

        Args:
            external_orders_data_list (list): List of external orders data.

        Returns:
            list: List of filtered external orders data.
        """
        self.ensure_one()

        filter_method_name = f'_filter_orders_{self.type_api}'

        if hasattr(self, filter_method_name):
            filter_method = getattr(self, filter_method_name)
            filtered_orders = filter_method(external_orders_data_list)
        else:
            filtered_orders = external_orders_data_list

        _logger.info(
            '%s: Orders filtered --> %s total; %s filtered out; %s remaining.',
            self.name,
            len(external_orders_data_list),
            len(external_orders_data_list) - len(filtered_orders),
            len(filtered_orders),
        )

        return filtered_orders

    @expose_for_testing('Import Orders')
    def integrationApiReceiveOrders(self, update_dt=True):
        """
        Receive and process orders from the integration source.

        Important: this is internal method, so it does not check if orders import is enabled.

        Args:
            update_dt (bool): Whether to update the 'last_receive_orders_datetime'
            attribute with the maximum 'updated_at' value from received orders.
            Defaults to True.

        Returns:
            recordset: A set of created input files for processed orders.
        """
        self.ensure_one()
        adapter = self.adapter
        last_receive_dt = self.last_receive_orders_datetime

        _logger.info(
            '%s receive orders: from kwargs %s',
            self.name,
            adapter.order_fetch_kwargs(),
        )

        # Update the actual sync timestamp
        self.last_order_sync_datetime = fields.Datetime.now()

        # 1. receive orders
        orders_data_list = adapter.receive_orders()

        # 2. filter orders
        filtered_orders_data_list = self.filter_received_orders(orders_data_list)

        # 3. create input files
        updated_at_list = list()
        created_input_files = self.env['sale.integration.input.file']

        for order_data in filtered_orders_data_list:
            input_file = self._create_input_file_from_received_data(order_data)
            created_input_files |= input_file

        # 4. update receive parameters
        updated_at_list = [order_data['updated_at'] for order_data in orders_data_list]
        if updated_at_list:
            last_receive_dt = self._find_max_datetime(updated_at_list)
        else:
            update_dt = False

        if update_dt:  # update
            self.last_receive_orders_datetime = last_receive_dt - timedelta(seconds=1)

        if len(orders_data_list) == adapter.order_limit_value():
            self.integration_receive_orders_cron()

        _logger.info(
            '%s receive orders: {count: %s, updated_at: %s, input_files: %s}',
            self.name,
            len(filtered_orders_data_list),
            last_receive_dt,
            created_input_files.ids,
        )
        return created_input_files

    @expose_for_testing('Clear Incorrect Attribute Value Mappings')
    def integrationApiClearIncorrectAttributeValueMappings(self):
        """Clear incorrect mappings for integration"""
        self.ensure_one()
        attribute_value_mappings = self.env['integration.product.attribute.value.mapping'].search([
            ('integration_id', '=', self.id),
            ('attribute_value_id', '!=', False),
        ])
        for value in attribute_value_mappings:
            if value.attribute_value_id:
                if value.attribute_value_id.attribute_id != value.get_attribute_id():
                    value.attribute_value_id = False
        return True

    def integration_receive_orders_cron(self, cron_operation=True):
        """
        Method called by the scheduled action to receive orders.
        This method checks if orders should be imported before proceeding.
        """
        self.ensure_one()

        # Check if orders import is enabled and exit early if not
        if not self.is_active:
            _logger.info(
                '%s: Order import skipped. Integration is not active or order import is disabled.',
                self.name
            )
            return False

        job_kwargs = self._job_kwargs_receive_orders(cron=cron_operation)

        context = {
            'company_id': self.company_id.id,
            'job_integration_id': self.id,
            'job_integration_job_type': 'order',
        }
        job = self \
            .with_context(**context) \
            .with_delay(**job_kwargs) \
            .integrationApiReceiveOrders(update_dt=cron_operation)

        return job

    def is_importable_order_status(self, statuses: list[str]) -> None:
        """
        Determines if an order should be imported based on its status.

        This method must be implemented by each connector as they have different
        status filtering mechanisms and formats.

        Args:
            statuses (list[str]): List of order statuses to validate. Typically contains
                                    only one status except for Shopify integration.

        Returns:
            bool: True if the order status is in the allowed list, False otherwise.

        Raises:
            NotImplementedError: This method must be implemented by each connector.
        """
        raise es.IntegrationNotImplementedError(_('Each connector has its own status filtering mechanism and format.'))

    def is_importable_order_date(self, date_order: str) -> bool:
        """
        Determines if an order should be imported based on its creation date and cut-off date.

        Args:
            date_order (str): The order creation date as a string (ISO format).

        Returns:
            bool: True if the order should be imported based on date, False otherwise.
                  Returns True if cut-off date is not configured or date parsing fails.
        """
        self.ensure_one()

        # If no cut-off date is configured, allow import
        if not self.orders_cut_off_datetime:
            return True

        # If no date is provided, allow import (let other validations handle it)
        if not date_order:
            return True

        try:
            order_creation_date = self._set_zero_time_zone(date_order)
            # Order should be imported if its creation date is >= cut-off date
            return order_creation_date >= self.orders_cut_off_datetime
        except Exception as e:
            _logger.warning(
                f'Failed to parse order creation date "{date_order}" for integration {self.name}: {e}. '
                'Skipping cut-off date check.'
            )
            # If parsing fails, allow import to avoid blocking valid orders
            return True

    def get_importable_order_statuses(self) -> None:
        """
        Retrieves the list of order statuses that are allowed for import.

        This method must be implemented by each connector as they have different
        status filtering mechanisms and formats.

        Returns:
            list[str]: List of allowed order statuses for import.
        Raises:
            NotImplementedError: This method must be implemented by each connector.
        """
        raise es.IntegrationNotImplementedError(_('Each connector has its own status filtering mechanism and format.'))

    def fetch_order_by_id_with_delay(self, external_order_id: str):
        """
        Create a sale order in Odoo based on the external order ID.
        """
        self.ensure_one()
        job_kwargs = self._job_kwargs_receive_order(external_order_id)

        context = {
            'company_id': self.company_id.id,
            'job_integration_id': self.id,
            'job_integration_job_type': 'order',
        }
        job = self \
            .with_context(**context) \
            .with_delay(**job_kwargs) \
            .fetch_order_by_id(external_order_id, raise_error=True)

        return job

    def update_order_status_by_id_with_delay(self, external_order_id: str, pipeline_data: dict):
        """
        Update the status of a sale order in Odoo based on the external order ID.
        The `pipeline_data` must contain at least the `integration_workflow_states` key.
        """
        self.ensure_one()
        job_kwargs = self._job_kwargs_update_status_order(external_order_id, pipeline_data)

        context = {
            'company_id': self.company_id.id,
            'job_integration_id': self.id,
            'job_integration_job_type': 'order',
        }
        job = self \
            .with_context(**context) \
            .with_delay(**job_kwargs) \
            .integration_update_status_order(external_order_id, pipeline_data)

        return job

    def cancel_order_by_id_with_delay(self, external_order_id: str, pipeline_data: dict):
        """
        Cancel a sale order in Odoo based on the external order ID.
        The `pipeline_data` must contain at least the `integration_workflow_states` key.
        """
        self.ensure_one()
        job_kwargs = self._job_kwargs_cancel_order(external_order_id)

        context = {
            'company_id': self.company_id.id,
            'job_integration_id': self.id,
            'job_integration_job_type': 'order',
        }
        job = self \
            .with_context(**context) \
            .with_delay(**job_kwargs) \
            .integration_update_status_order(
                external_order_id,
                pipeline_data,
                cancel_order=True,
            )

        return job

    def integration_update_status_order(self, external_order_id: str, pipeline_data: dict, cancel_order: bool = False):
        """
        Update the status of a sale order in Odoo based on the external order ID.
        The `pipeline_data` must contain at least the `integration_workflow_states` key.
        """
        self.ensure_one()

        input_file = self._get_input_file(external_order_id)

        if not input_file:
            _logger.info(f'External data for order with code={external_order_id} not found!')
            raise es.ApiImportError(
                f'{self.name} (update order status): Order with code={external_order_id} not found!'
                f'Most likely it was not imported (due to import order status filter).'
            )

        if cancel_order:
            if input_file.order_id:
                return input_file._run_cancel_order(pipeline_data)
            return False

        return input_file._build_and_run_order_pipeline(pipeline_data)

    def fetch_order_by_id(self, external_order_id: str, raise_error: bool = False):
        self.ensure_one()

        input_data = self.adapter.receive_order(external_order_id)

        # Handle case where input data is not found for the external order
        if not input_data:
            message = _(
                '%s: Failed to receive order. External order with ID "%s" was not found.\n\n'
                'This could be due to one of the following reasons:\n'
                '- The order ID is incorrect (please double-check the ID).\n'
                '- The order has been removed from the external system.\n\n'
                'Please verify the external order ID or check the order in the external system.'
            ) % (self.name, external_order_id)
            _logger.info(message)

            if raise_error:
                raise es.ApiImportError(message)
            return False

        filtered_input_data = self.filter_received_orders([input_data])

        if not filtered_input_data:
            _logger.info('%s: Order with code=%s skipped by integration filter-rules!', self.name, external_order_id)
            return False

        # Create input file from received data
        input_file = self._create_input_file_from_received_data(filtered_input_data[0])

        _logger.info(
            '%s: Successfully received order. Created input file "%s" from external order ID "%s".',
            self.name,
            input_file,
            external_order_id,
        )
        return input_file

    def create_product_by_id_with_delay(self, external_product_id: str):
        """
        Create a product in Odoo based on the external product ID.
        """
        self.ensure_one()

        job_kwargs = self._job_kwargs_import_product(
            external_product_id,
            self.env.context.get('external_product_name') or '',
        )
        job_kwargs['eta'] = 8

        context = {
            'company_id': self.company_id.id,
            'job_integration_id': self.id,
            'job_integration_job_type': 'product',
        }
        job = self.with_context(**context) \
            .with_delay(**job_kwargs) \
            .import_product_flow(external_product_id)

        return job

    def update_product_by_id_with_delay(self, external_product_id: str, check_hook_gap: bool = False):
        """
        Update a product in Odoo based on the external product ID.
        """
        self.ensure_one()

        # Check if the product exists in Odoo, if not, create it.
        external_product = self._get_external_product(external_product_id)
        if not external_product:
            return self.create_product_by_id_with_delay(external_product_id)

        # Check if the product is mapped to an Odoo record, if not, drop it and create a new external product.
        mapping_record = external_product.mapping_record
        if not mapping_record.odoo_record:
            self.drop_external_record(external_product.id)
            return self.create_product_by_id_with_delay(external_product_id)

        if check_hook_gap:
            export_timedelta = self.get_settings_value('receive_webhook_gap', default_value=0)
            if (external_product.current_time - external_product.timestamp_export) <= int(export_timedelta):
                _logger.info(
                    '%s: Product with code=%s is not updated because the hook gap is less than the export timedelta',
                    self.name,
                    external_product_id,
                )
                return False

        job_kwargs = self._job_kwargs_update_product_in_odoo(
            external_product_id,
            self.env.context.get('external_product_name') or '',
        )

        context = {
            'company_id': self.company_id.id,
            'job_integration_id': self.id,
            'job_integration_job_type': 'product',
            'job_external_template_id': external_product.id,
        }
        job = external_product \
            .with_context(**context) \
            .with_delay(**job_kwargs) \
            .import_one_product_by_hook(check_hook_gap)

        return job

    def delete_product_by_id_with_delay(self, external_product_id: str):
        """
        Delete a product in Odoo based on the external product ID.
        """
        self.ensure_one()

        external_product = self._get_external_product(external_product_id)
        if not external_product:
            _logger.info(f"Product with code={external_product_id} not found!")
            return True

        job_kwargs = self._job_kwargs_delete_product(external_product.code, external_product.name)

        context = {
            'company_id': self.company_id.id,
            'job_integration_id': self.id,
            'job_integration_job_type': 'product',
        }
        job = self.with_context(**context) \
            .with_delay(**job_kwargs) \
            .drop_external_record(external_product.id)

        return job

    def process_pipeline_by_id_with_delay(self, external_order_id: str, data: dict, build_and_run: bool = False):
        """
        Process a pipeline in Odoo based on the external order ID.
        """
        self.ensure_one()

        job_kwargs = self._job_kwargs_process_pipeline(external_order_id)

        context = {
            'company_id': self.company_id.id,
            'job_integration_id': self.id,
            'job_integration_job_type': 'order',
        }
        job = self.with_context(**context) \
            .with_delay(**job_kwargs) \
            .integration_process_pipeline(external_order_id, data, build_and_run=build_and_run)

        return job

    def integration_process_pipeline(self, external_order_id: str, data: dict, build_and_run: bool = False):
        self.ensure_one()

        input_file = self._get_input_file(external_order_id)
        if not input_file:
            _logger.info(
                f'Input file for order with code={external_order_id} not found!'
            )
            return False

        if build_and_run:
            return input_file._build_and_run_order_pipeline(data)

        return input_file.run_actual_pipeline()

    def _create_input_file_from_received_data(self, input_data: dict):
        InputFile = self.env['sale.integration.input.file']
        domain = [
            ('si_id', '=', self.id),
            ('name', '=', input_data['id']),
        ]
        exists = InputFile.search(domain, limit=1)

        if exists:
            return InputFile

        vals = {
            **{k: v for k, __, v in domain},
            'raw_data': json.dumps(input_data['data'], indent=4),
            'update_required': True,
        }
        return InputFile.create(vals)

    @expose_for_testing('Run Inventory Export for All Products')
    def integrationApiExportInventory(self):
        """
        Method called by the scheduled action to export inventory.
        This method checks if inventory sync should be performed before proceeding.
        """
        self.ensure_one()

        # Check if periodic inventory sync is enabled and exit early if not
        if not self.is_active:
            _logger.info(
                '%s: Periodic inventory sync skipped. '
                'Connection to the e-commerce store is not active or periodic inventory sync is disabled.',
                self.name
            )
            return False

        products = self.env['product.product'].search([
            ('type', '=', 'consu'),
            ('is_storable', '=', True),
            ('integration_ids.id', '=', self.id),
            ('exclude_from_synchronization', '=', False),
            ('exclude_from_synchronization_stock', '=', False),
        ])
        return products.export_inventory_by_jobs(self, cron_operation=True)

    def is_canceled_order_status(self, status_code: str) -> bool:
        """
        Determines if the given status code represents a canceled order.

        This method extracts the store order status ID from the provided status code
        and checks if it matches the predefined cancel status ID.

        Args:
            status_code (str): The order status code to evaluate.

        Returns:
            bool: True if the status code indicates a canceled order, False otherwise.
        """
        sub_status_id, _ = self._get_order_sub_status_tuple(status_code)
        return sub_status_id == self.sub_status_cancel_id

    def update_last_update_pricelist_items_to_now(self, value):
        self.last_update_pricelist_items = value

    def create_order_from_input(self, input_file_id: int) -> 'models.Model':
        self.ensure_one()

        # 1. Create factory and build the sale order (parsing happens inside)
        factory = self.env['integration.sale.order.factory'] \
            .with_company(self.company_id) \
            .create({'input_file_id': input_file_id})
        order = factory.create_order()

        input_file = factory.input_file_id

        # 2. If the order is canceled on the store side, cancel it in Odoo
        if factory.is_cancelled:
            _logger.info(f'Order "{order.name}" has been canceled on the store side. Canceling it in Odoo.')

            order._integration_action_cancel_no_dispatch()
            input_file.action_done()
            return order

        # 3. Process the order automatic workflow
        input_file.action_process()
        order._build_and_run_integration_workflow(
            workflow_states=factory.workflow_states,
            payment_method_code=factory.payment_method_code,
        )

        return order

    @expose_for_testing('Create Sales Orders (Using Imported External Orders)')
    def integrationApiCreateOrders(self):  # Seems this one not used currently
        self.ensure_one()

        input_files = self.env['sale.integration.input.file'].search([
            ('si_id', '=', self.id),
            ('state', '=', 'draft'),
        ])

        orders = self.env['sale.order']
        for input_file in input_files:
            orders += self.create_order_from_input(input_file.id)

        return orders

    def _get_mapping_friendly_name(self, model_name):
        """Get user-friendly plural label from mapping model's _mapping_label attribute."""
        mapping_model = self.env[model_name]

        # Check if the model has a _mapping_label attribute
        if hasattr(mapping_model, '_mapping_label') and mapping_model._mapping_label:
            return pluralize(mapping_model._mapping_label)

        # Fallback: generate from model name
        # e.g., 'integration.product.mapping' -> 'Products'
        name = model_name.replace('integration.', '').replace('.mapping', '').replace('.', ' ').title()
        return pluralize(name)

    @api.model
    def get_status_menu_data(self):
        integrations = self.sudo().search([
            ('state', '=', 'active'),
        ])

        result = []
        mapping_models = self.integration_mapping_models()

        for integration in integrations:
            failed_jobs_count = integration._get_integration_failed_jobs_count()
            orders_count = self.env['sale.integration.input.file'].search_count([
                ('si_id', '=', integration.id),
            ])
            unprocessed_orders_count = self.env['sale.integration.input.file'].search_count([
                ('si_id', '=', integration.id),
                ('order_id', '=', False),
            ])
            products_count = self.env['integration.product.template.mapping'].search_count([
                ('integration_id', '=', integration.id),
            ])

            missing_mappings_count = 0
            missing_mappings_by_type = []

            for model_name in mapping_models:
                mapping_model = self.env[model_name]
                internal_field_name, external_field_name = mapping_model._mapping_fields
                missing_mappings = mapping_model.search_count([
                    ('integration_id', '=', integration.id),
                    (internal_field_name, '=', False),
                    (external_field_name, '!=', False),
                ])

                if missing_mappings > 0:
                    type_name = self._get_mapping_friendly_name(model_name)
                    missing_mappings_by_type.append({
                        'type': type_name,
                        'count': missing_mappings,
                        'model': model_name,
                    })

                missing_mappings_count += missing_mappings

            # Sort missing mappings alphabetically by type name
            missing_mappings_by_type.sort(key=lambda x: x['type'])

            integration_stats = {
                'id': integration.id,
                'name': integration.name,
                'type_api': integration.type_api,
                'orders_count': orders_count,
                'unprocessed_orders_count': unprocessed_orders_count,
                'products_count': products_count,
                'failed_jobs_count': failed_jobs_count,
                'missing_mappings_count': missing_mappings_count,
                'missing_mappings_by_type': missing_mappings_by_type,
            }
            result.append(integration_stats)

        return result

    @api.model
    def get_failed_jobs_action(self, integration_id):
        """Return the failed jobs action for a specific integration (called from JS)."""
        action = self.env['ir.actions.act_window']._for_xml_id(
            'integration.integration_jobs_action'
        )
        action['name'] = _('Failed Jobs')
        action['domain'] = [
            ('integration_id', '=', integration_id),
            ('state', '=', 'failed'),
        ]
        action['context'] = {
            'search_default_failed': 1,
            'default_integration_id': integration_id,
        }
        return action

    @ormcache()
    def integration_mapping_models(self):
        result = list()
        for model_name in self.env:
            if (
                model_name.startswith('integration.')
                and model_name.endswith('.mapping')
                and model_name not in EXCLUDED_MAPPING_MODELS
            ):
                result.append(model_name)
        return result

    def _get_integration_failed_jobs_count(self):
        failed_jobs_count = self.env['queue.job'].search_count([
            ('state', '=', 'failed'),
            ('integration_id', '=', self.id),
            ('company_id', '=', self.company_id.id)
        ])
        return failed_jobs_count

    @api.model
    def _get_test_method(self):
        """
        Get all methods marked with @expose_for_testing decorator.
        Returns list of tuples: (method_name, friendly_name)
        """
        test_methods = []

        for method_name in dir(self):
            if method_name.startswith('_') or method_name == '<lambda>':
                continue

            try:
                method = getattr(self, method_name, None)

                # Check if it's a callable method exposed for testing
                if callable(method) and getattr(method, '_expose_for_testing', False):
                    label = getattr(method, '_testing_label', method_name)
                    test_methods.append((method_name, label))
            except Exception:
                # Skip methods that cause issues during introspection. We use Exception to catch
                # all errors because there may be different types of them and issues
                # with this debug feature shouldn't affect the main functionality.
                continue

        test_methods.sort(key=lambda x: x[1])

        return test_methods

    def run_test_method(self):
        method_name = self.test_method
        if not method_name:
            raise UserError(_(
                'No test method selected.\n\n'
                'Please select a test method from the dropdown above before clicking the button.'
            ))

        # Check if the method exists on the current object
        test_method = getattr(self, method_name, None)
        if test_method:
            return test_method()

        # If the method doesn't exist, log the issue and return True
        raise UserError(_(
            'The selected test method "%s" does not exist on the object.\n\n'
            'Please select a valid test method from the dropdown above.'
        ) % method_name)

    def _set_default_advanced_fields(self, force: bool = False):
        for rec in self.with_context(skip_write_actions=True).filtered(lambda x: not x.is_no_api):
            if force:
                rec.template_reference_id.mark_mapping_inactive(rec.id)
                rec.product_reference_id.mark_mapping_inactive(rec.id)

                rec.template_barcode_id.mark_mapping_inactive(rec.id)
                rec.product_barcode_id.mark_mapping_inactive(rec.id)

            rec._ensure_ecommerce_field('template_reference_id', set_default=force)
            rec._ensure_ecommerce_field('product_reference_id', set_default=force)

            rec._ensure_ecommerce_field('template_barcode_id', set_default=force)
            rec._ensure_ecommerce_field('product_barcode_id', set_default=force)

    def _ensure_ecommerce_field(self, name, set_default: bool = False):
        """
        :name:
            - Name of the m2o field pointed to the Ecommerce Field --> product.ecommerce.field
        """
        if set_default:
            getattr(self, f'_set_default_{name}', lambda: False)()

        efield = getattr(self, name)

        if not efield:
            if not getattr(self, f'_set_default_{name}', lambda: False)():
                raise UserError(_(
                    '%s: The essential field "%s" is not defined.\n\n'
                    'This field is required for the proper functioning of the integration. '
                    'Please ensure that the field is set correctly in the eCommerce settings.'
                ) % (self.name, name))

            efield = getattr(self, name)

        efield._ensure_mapping(self.id)

        return efield

    @property
    def product_reference_name(self):
        ecommerce_id = self._ensure_ecommerce_field('product_reference_id')
        return ecommerce_id.odoo_field_name

    @property
    def product_barcode_name(self):
        ecommerce_id = self._ensure_ecommerce_field('product_barcode_id')
        return ecommerce_id.odoo_field_name

    @property
    def template_reference_api_name(self):
        ecommerce_id = self._ensure_ecommerce_field('template_reference_id')
        return ecommerce_id.technical_name

    @property
    def variant_reference_api_name(self):
        ecommerce_id = self._ensure_ecommerce_field('product_reference_id')
        return ecommerce_id.technical_name

    @property
    def template_barcode_api_name(self):
        ecommerce_id = self._ensure_ecommerce_field('template_barcode_id')
        return ecommerce_id.technical_name

    @property
    def variant_barcode_api_name(self):
        ecommerce_id = self._ensure_ecommerce_field('product_barcode_id')
        return ecommerce_id.technical_name

    def _get_reference_field_name(self, odoo_model):
        if odoo_model._name in ('product.template', 'product.product'):
            return self.product_reference_name

        reference_field = getattr(odoo_model, '_internal_reference_field', None)
        if not reference_field:
            # Raise a custom exception with a clear, user-friendly message
            raise es.NoReferenceFieldDefined(_(
                'The model "%s" does not have an internal reference field defined (_internal_reference_field).\n\n'
                'This field is required for integration purposes. Please ensure that the model is properly configured '
                'or contact support for assistance.'
            ) % odoo_model._name)

        return reference_field

    def get_template_hub_class(self):
        return TemplateHub

    def _get_product_validation_domain(self):
        return [
            ('product_tmpl_id.exclude_from_synchronization', '=', False),
        ]

    def is_barcode_validation_required(self):
        if not self.validate_barcode:
            return False

        self._ensure_ecommerce_field('template_barcode_id')
        self._ensure_ecommerce_field('product_barcode_id')

        mapping_ids = (
            self.template_barcode_id._get_mapping_for_integration(self.id)
            + self.product_barcode_id._get_mapping_for_integration(self.id)
        )

        # Raise an error if no mappings are found
        if not mapping_ids:
            raise UserError(_(
                'Barcode validation is enabled, but no active mappings exist for the barcode fields '
                'between Odoo and the e-commerce system.\n\n'
                'To proceed, please add the required mappings for barcode fields in the integration settings, '
                'or disable the "Variant Barcode Validation" property if barcode validation is not needed.'
            ))

        return True

    def _validate_product_templates(self):
        """
        Validate product templates and return structured validation results.

        This method performs comprehensive validation of product data in both the e-commerce
        system and Odoo, checking for various issues like missing references, duplicated
        barcodes, configuration problems, etc.

        Args:
            show_message (bool): If True, raises UserError when no issues found

        Returns:
            dict: Structured validation results with the following structure:
                {
                    'ecommerce_system': {
                        'missing_references': {
                            'title': str,
                            'items': list,
                        },
                        'partial_barcodes': {
                            'title': str,
                            'items': list,
                        },
                        'missing_variant_references': {
                            'title': str,
                            'items': list,
                        },
                        'repeated_configurations': {
                            'title': str,
                            'items': dict,
                            'is_dict': True,
                            'wrap_key': True,
                        },
                        'nested_configurations': {
                            'title': str,
                            'items': dict,
                            'is_dict': True,
                            'wrap_key': True,
                        },
                        'duplicated_references': {
                            'title': str,
                            'items': dict,
                            'is_dict': True,
                        },
                        'duplicated_barcodes': {
                            'title': str,
                            'items': dict,
                            'is_dict': True,
                        },
                    },
                    'odoo_system': {
                        'missing_variant_references': {
                            'title': str,
                            'items': list,
                        },
                        'duplicated_references': {
                            'title': str,
                            'items': dict,
                            'is_dict': True,
                        },
                        'duplicated_barcodes': {
                            'title': str,
                            'items': dict,
                            'is_dict': True,
                        },
                    },
                    'has_errors': bool,
                }

        Example usage:
            # Get validation results
            results = integration._validate_product_templates()

            # Check if there are any errors
            if results['has_errors']:
                # Process e-commerce errors
                for error_type, error_data in results['ecommerce_system'].items():
                    print(f"E-commerce error: {error_data['title']}")

                # Process Odoo errors
                for error_type, error_data in results['odoo_system'].items():
                    print(f"Odoo error: {error_data['title']}")
        """
        tmpl_hub = self.adapter.get_templates_and_products_for_validation_test()

        ref_field = self.product_reference_name
        barcode_field = self.product_barcode_name
        ref_field_name = self.env['product.template']._get_field_string(ref_field)

        # Get product validation results from the e-commerce system
        template_ids, variant_ids = tmpl_hub.get_products_with_empty_references()
        repeated_configurations = tmpl_hub.get_products_with_repeated_configurations()
        nested_configurations = tmpl_hub.get_products_with_nested_configurations()
        duplicated_ref = tmpl_hub.get_products_with_duplicate_references()

        check_barcodes = self.is_barcode_validation_required()

        if check_barcodes:
            part_fill_bar = tmpl_hub.get_products_with_partial_barcodes()
            duplicated_bar = tmpl_hub.get_products_with_duplicate_barcodes()
        else:
            part_fill_bar = duplicated_bar = False

        # Build validation results structure
        validation_results = {
            'ecommerce_system': {},
            'odoo_system': {},
            'has_errors': False,
        }

        # E-commerce system validation
        ecommerce_errors = {}

        # Missing reference fields in the e-commerce system
        if template_ids:
            ecommerce_errors['missing_references'] = {
                'title': _('Products without "%s" in the e-Commerce system:') % ref_field_name,
                'items': template_ids,
            }

        # Partially filled barcodes
        if part_fill_bar:
            ecommerce_errors['partial_barcodes'] = {
                'title': _('Products with partially filled barcodes on variants in the e-Commerce system:'),
                'items': part_fill_bar,
            }

        # Missing reference fields in product variants
        if variant_ids:
            ecommerce_errors['missing_variant_references'] = {
                'title': _('Product variants IDs without "%s" in e-Commerce System:') % ref_field_name,
                'items': variant_ids,
            }

        # Repeated configurations in the e-commerce system
        if repeated_configurations:
            ecommerce_errors['repeated_configurations'] = {
                'title': _('Simple products assigned to multiple configurable products:'),
                'items': repeated_configurations,
                'is_dict': True,
                'wrap_key': True,
            }

        # Nested configurable products
        if nested_configurations:
            ecommerce_errors['nested_configurations'] = {
                'title': _('Configurable Product contains another Configurable Product.'),
                'items': nested_configurations,
                'is_dict': True,
                'wrap_key': True,
            }

        # Duplicated references in the e-commerce system
        if duplicated_ref:
            ecommerce_errors['duplicated_references'] = {
                'title': _('Duplicated references in the e-Commerce system:'),
                'items': duplicated_ref,
                'is_dict': True,
            }

        # Duplicated barcodes in the e-commerce system
        if duplicated_bar:
            ecommerce_errors['duplicated_barcodes'] = {
                'title': _('Duplicated barcodes in e-Commerce System:'),
                'items': duplicated_bar,
                'is_dict': True,
            }

        if ecommerce_errors:
            validation_results['ecommerce_system'] = ecommerce_errors
            validation_results['has_errors'] = True

        # Now validate Odoo products
        search_product_domain = self._get_product_validation_domain()
        field_list = [  # Don't touch fields sequence
            'id', 'name', barcode_field, ref_field, 'product_tmpl_id',
        ]
        odoo_variant_ids = self.env['product.product'].search_read(
            search_product_domain,
            fields=field_list,
        )
        tmpl_hub_odoo = tmpl_hub.__class__.from_odoo(
            odoo_variant_ids, reference=ref_field, barcode=barcode_field)

        __, variant_odoo_ids = tmpl_hub_odoo.get_products_with_empty_references()
        duplicated_ref_odoo = tmpl_hub_odoo.get_products_with_duplicate_references()

        if check_barcodes:
            duplicated_bar_odoo = tmpl_hub_odoo.get_products_with_duplicate_barcodes()
        else:
            duplicated_bar_odoo = False

        # Odoo system validation
        odoo_errors = {}

        # Missing reference fields in Odoo product variants
        if variant_odoo_ids:
            odoo_errors['missing_variant_references'] = {
                'title': _('Product variants without "%s" in Odoo:') % ref_field_name,
                'items': variant_odoo_ids,
            }

        # Duplicated references in Odoo
        if duplicated_ref_odoo:
            odoo_errors['duplicated_references'] = {
                'title': _('Duplicated references in Odoo:'),
                'items': duplicated_ref_odoo,
                'is_dict': True,
            }

        # Duplicated barcodes in Odoo
        if duplicated_bar_odoo:
            odoo_errors['duplicated_barcodes'] = {
                'title': _('Duplicated barcodes in Odoo:'),
                'items': duplicated_bar_odoo,
                'is_dict': True,
            }

        if odoo_errors:
            validation_results['odoo_system'] = odoo_errors
            validation_results['has_errors'] = True

        return validation_results

    def _get_product_validation_report_html(self):
        validation_results = self._validate_product_templates()

        if not validation_results['has_errors']:
            return ''

        formatter = HtmlWrapper(self)

        # Format E-commerce system errors
        if validation_results['ecommerce_system']:
            formatter.add_title(_('E-COMMERCE PRODUCTS VALIDATION'))

            for error_type, error_data in validation_results['ecommerce_system'].items():
                if error_data.get('is_dict'):
                    if error_data.get('wrap_key'):
                        formatter.add_sub_block_for_external_product_dict(
                            error_data['title'],
                            error_data['items'],
                            wrap_key=True,
                        )
                    else:
                        formatter.add_sub_block_for_external_product_dict(
                            error_data['title'],
                            error_data['items'],
                        )
                else:
                    formatter.add_sub_block_for_external_product_list(
                        error_data['title'],
                        error_data['items'],
                    )

        # Format Odoo system errors
        if validation_results['odoo_system']:
            formatter.add_title(_('ODOO PRODUCTS VALIDATION'))

            for error_type, error_data in validation_results['odoo_system'].items():
                if error_data.get('is_dict'):
                    if error_type == 'duplicated_references':
                        formatter.add_sub_block_for_internal_variant_dict(
                            error_data['title'],
                            error_data['items'],
                        )
                    elif error_type == 'duplicated_barcodes':
                        formatter.add_sub_block_for_internal_variant_dict(
                            error_data['title'],
                            error_data['items'],
                        )
                else:
                    if error_type == 'missing_variant_references':
                        formatter.add_sub_block_for_internal_variant_list(
                            error_data['title'],
                            error_data['items'],
                        )

        return formatter.dump()

    @raise_requeue_job_on_concurrent_update
    def import_product(
        self,
        external_template_id: int,
        import_images: bool = False,
        trigger_export_other: bool = False,
    ):
        """
        :external_template_id:
            - int (ID of the `integration.product.template.external` ORM record)
        """
        self.ensure_one()

        external_template = self.env['integration.product.template.external'] \
            .browse(external_template_id)

        template_data, variants_data, bom_data, external_images = self.adapter \
            .get_product_for_import(external_template.code)

        try:
            template = external_template\
                .with_context(integration_import_images=import_images) \
                ._import_one_product(template_data, variants_data, bom_data, external_images)
        except OperationalError:
            raise
        except Exception as ex:
            raise ValidationError(_(
                'Failed to import the product from the external system.\n\n'
                'Debug Information:\n\nError: %s\n\n'
                'External Template Code: %s\n\n'
                'Template Data:\n\t%s\n\n'
                'Variants Data:\n\t%s\n\n'
                'BOM Data:\n\t%s\n\n'
            ) % (ex.args[0], external_template.code, template_data, variants_data, bom_data))

        template = template.with_context(skip_product_export=False)

        if trigger_export_other:
            for integration in template.integration_ids.filtered(lambda x: x != self):
                template.trigger_export(export_images=import_images, force_integrations=integration)

        return template

    def import_product_flow(self, external_template_id: str):
        """
        Full import for the new product (not existing in DB):
            a) create an external-record
            b) run full import for the external-record
        """
        self.ensure_one()

        if self._get_external_product(external_template_id):
            return False

        external_template, __, errors, __ = self._import_external_product(external_template_id)

        if errors:
            _logger.warning(f'Errors during template import {external_template_id}:\n' + '\n'.join(errors))

        if not external_template:
            _logger.warning(f'External product {external_template_id} could not be imported.')
            return False

        odoo_record = external_template.odoo_record
        if odoo_record or self.auto_create_products_on_so:
            # Calling the method to update the product in Odoo.
            # Example: In WooCommerce with multi-language enabled, if a translated product is modified,
            # the connector receives the translated product's ID but the API returns the main product instead.
            # Since the main product already exists in Odoo, no update occurs for the translated version.

            odoo_record = external_template \
                .import_one_product(import_images=self.allow_import_images)

        return odoo_record

    def drop_external_record(self, odoo_external_product_id):
        record = self.env['integration.product.template.external'].browse(odoo_external_product_id)
        record_format = record.format_recordset()
        return record_format, record.unlink()

    def action_run_integration_auth(self):
        self.ensure_one()

        action = self._get_integration_auth_action()

        return action

    def create_auth_wizard(self):
        self.ensure_one()
        action = self._get_integration_auth_action()

        model_name = action['res_model']
        context = action['context']

        return self.env[model_name] \
            .with_context(**context) \
            .create({'integration_id': self.id})

    def _get_integration_auth_action(self, *args, **kw):
        raise NotImplementedError

    def action_run_configuration_wizard(self):
        self.ensure_one()

        self._raise_if_not_access_granted()

        wizard = self._build_configuration_wizard()
        wizard.init_configuration()

        return wizard.get_action_view()

    def action_run_import_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('What Would You Like to Do?'),
            'res_model': 'integration.import.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_integration_id': self.id,
            },
        }

    def _build_configuration_wizard(self):
        integration_postfix = self._get_configuration_postfix()

        wizard = self.env['configuration.wizard.' + integration_postfix].search(
            [('integration_id', '=', self.id)],
            limit=1,
        )

        if not wizard:
            wizard = wizard.create({'integration_id': self.id})

        return wizard

    def _should_link_parent_contact(self):
        # Since we are having `external_company_name` this one may de dropped.
        return True

    def force_set_inactive(self):
        return {'active': False}

    def _set_zero_time_zone(self, external_date, to_string=False):
        """
        Set time zone to UTC+0
        :param external_date - datetime as a string or datetime class
        :return: datetime object with time zone UTC+0
        """
        if isinstance(external_date, str):
            try:
                # Try ISO format first (handles formats like "2025-11-07T10:23:54" and "2025-06-12T15:42:12+02:00")
                external_date = parser.isoparse(external_date)
            except (ValueError, TypeError):
                # Fallback to flexible parser for formats like "2025-10-08 15:59:31" (SQL datetime format)
                external_date = parser.parse(external_date)

        if external_date.tzinfo:
            external_date = external_date.astimezone(pytz.utc).replace(tzinfo=None)

        if to_string:
            return datetime.strftime(external_date, DATETIME_FORMAT)
        return external_date

    def _find_max_datetime(self, datetime_list: list):
        """
        Find the maximum datetime from a list of datetimes.

        Args:
            datetime_list (list): List of datetimes.

        Returns:
            datetime: Maximum datetime.
        """
        if not datetime_list:
            return None

        date_max = max(x for x in datetime_list)
        return self._set_zero_time_zone(date_max)

    def _job_kwargs_receive_orders(self, cron=True):
        return {
            'priority': 6,
            'description': f'{self.name}: Receive Orders (cron={cron})',
            'identity_key': f'receive_orders_cron-{self.type_api}_{self.id}',
        }

    def _job_kwargs_receive_order(self, order_id):
        source = self.env.context.get('integration_event_source', '')
        return {
            'eta': 8,
            'priority': 7,
            'description': f'{self.name}: Receive One Order (id={order_id}){f" [{source}]" if source else ""}',
            'identity_key': f'receive_order-{self.type_api}_{self.id}_{order_id}',
        }

    def _job_kwargs_update_status_order(self, order_id, pipeline_data=None):
        source = self.env.context.get('integration_event_source', '')

        # Extract status information from pipeline_data for identity key
        status_code = 'empty_status'
        if pipeline_data and pipeline_data.get('integration_workflow_states'):
            # Get the first status from the list
            status_code = pipeline_data['integration_workflow_states'][0]

        return {
            'eta': 8,
            'priority': 9,
            'description': f'{self.name}: Update Order Status (id={order_id}){f" [{source}]" if source else ""}',
            'identity_key': f'update_order_status-{self.type_api}_{self.id}_{order_id}_{status_code}',
        }

    def _job_kwargs_cancel_order(self, order_id):
        source = self.env.context.get('integration_event_source', '')

        return {
            'eta': 8,
            'priority': 9,
            'description': f'{self.name}: Cancel Order (id={order_id}){f" [{source}]" if source else ""}',
            'identity_key': f'cancel_order-{self.type_api}_{self.id}_{order_id}',
        }

    def _job_kwargs_export_template(self, template, export_images, force=False):
        return {
            'eta': int(self.get_settings_value('export_template_delay', default_value=0)),
            'priority': 11,
            'identity_key': (
                f'export_template-{self.id}_{template}_{int(export_images)}_{int(force)}'
            ),
            'description': f'{self.name}: Export Single Product "{template.display_name}"',
        }

    def _job_kwargs_import_product(self, external_id, name):
        source = self.env.context.get('integration_event_source', '')
        description = (
            f'{self.name}: Import External Product "{name}" [{external_id}]'
            f'{f" [{source}]" if source else ""}'
        )
        return {
            'priority': 17,
            'identity_key': f'import_external_product-{self.id}-{external_id}',
            'description': description,
        }

    def _job_kwargs_update_product_in_odoo(self, external_id, name):
        source = self.env.context.get('integration_event_source', '')
        description = (
            f'{self.name}: Update External Product "{name}" [{external_id}] in Odoo'
            f'{f" [{source}]" if source else ""}'
        )

        return {
            'eta': 10,
            'priority': 17,
            'identity_key': f'update_external_product-{self.id}-{external_id}',
            'description': description,
        }

    def _job_kwargs_delete_product(self, external_id, name):
        source = self.env.context.get('integration_event_source', '')
        description = (
            f'{self.name}: Delete External Product "{name}" [{external_id}] in Odoo'
            f'{f" [{source}]" if source else ""}'
        )
        return {
            'priority': 17,
            'identity_key': f'delete_external_product-{self.id}-{external_id}',
            'description': description,
        }

    def _job_kwargs_process_pipeline(self, external_order_id):
        source = self.env.context.get('integration_event_source', '')
        description = (
            f'{self.name}: Process Pipeline for Order "{external_order_id}"'
            f'{f" [{source}]" if source else ""}'
        )
        return {
            'priority': 9,
            'identity_key': f'process_pipeline-{self.id}_{external_order_id}',
            'description': description,
        }

    def _job_kwargs_export_images(self, template):
        return {
            'eta': 5,
            'priority': 12,
            'identity_key': f'export_images-{self.id}-{template}',
            'description': f'{self.name}: Export Images for the Product "{template.display_name}"',
        }

    def _job_kwargs_import_images(self, template):
        return {
            'priority': 18,
            'identity_key': f'import_images-{self.id}-{template}',
            'description': f'{self.name}: Import Images for the Product "{template.display_name}"',
        }

    def _job_kwargs_export_inventory_variant(self, variant, cron=True):
        return {
            'priority': 13,
            'identity_key': f'export_inventory-{self.id}-{variant}',
            'description': (
                f'{self.name}: Export Inventory for the Product Variant "{variant.display_name}" (cron={cron})'
            ),
        }

    def _job_kwargs_create_order_from_input(self, input_file):
        return {
            'priority': 8,
            'identity_key': f'create_order-{self.id}-{input_file}',
            'eta': 60 * int(self.get_settings_value('process_order_delay') or 0),
            'description': f'{self.name}: Create Order from Input File "{input_file.display_name}"',
        }

    def _job_kwargs_export_specific_prices_template(self, template):
        return {
            'priority': 16,
            'identity_key': f'export_specific_prices-{self.id}-{template}',
            'description': (
                f'{self.name}: Export Specific Prices for "{template.display_name}" template'
            ),
        }

    def _job_kwargs_prepare_specific_prices(self, pricelist_ids):
        ids = '-'.join(map(str, pricelist_ids.ids))
        names = ', '.join(pricelist_ids.mapped('name'))
        return {
            'priority': 14,
            'identity_key': f'prepare_prices_from_pricelists-{self.id}_{ids}',
            'description': (
                f'{self.name}: Export. Prepare Specific Prices from Pricelists ({names})'
            ),
        }

    def _job_kwargs_export_specific_prices_data(self, idx):
        return {
            'priority': 15,
            'identity_key': f'export_specific_prices_block-{self.id}-{idx}',
            'description': f'{self.name}: Export Specific Prices ({idx})',
        }

    def _job_kwargs_apply_stock_single(self, external_id, location):
        name = f'{external_id} → {location.display_name}'
        return {
            'priority': 4,
            'identity_key': f'integration-apply-stock-single_{self.id}-{external_id}-{location.id}',
            'description': f'{self.name}: Apply Stock Levels for Single Product: {name}',
        }

    def _job_kwargs_apply_stock_multi(self, location_line, block=1):
        location_id = location_line.id
        location_name = location_line.erp_location_id.display_name
        return {
            'priority': 3,
            'identity_key': f'integration-apply-stock-multi_{self.id}-{location_id}-{block}',
            'description': f'{self.name}: Apply Stock Levels to "{location_name}" ({block})',
        }

    def _job_kwargs_import_stock_from_location(self, location_line, block=1):
        location_id = location_line.erp_location_id.id
        location_name = location_line.erp_location_id.display_name

        ext_location_id = location_line.external_location_id.id
        ext_location_name = location_line.external_location_id.name or self.name

        complex_id = f'{ext_location_id}-{location_id}'
        complex_name = f'{ext_location_name} → {location_name}'

        return {
            'priority': 3,
            'identity_key': f'integration-import-stock-location_{self.id}-{complex_id}-{block}',
            'description': f'{self.name}: Import Stock Levels for "{complex_name}" ({block})',
        }

    def _job_kwargs_import_single_customer(self, customer_id):
        return {
            'priority': 4,
            'description': f'{self.name}: Import for Single Customer "%s"' % customer_id,
            'identity_key': f'integration_import_single_customer-{self.id}-{customer_id}',
        }

    def _job_kwargs_export_picking(self, picking):
        return {
            'priority': 10,
            'identity_key': f'integration_send_picking-{self.id}-{picking.id}',
            'description': f'{self.name}: Send Picking "{picking.name}" ({picking.id})',
        }

    def get_integration_lang_code(self):
        """
        Returns the language code (e.g., `en_US`) based on the `integration_lang_id` field value.
        Essential conditions: the language must be required and active.
        """
        self.ensure_one()

        lang = self.integration_lang_id

        if not lang:
            raise UserError(_(
                '%s: Integration language is not defined.\n\n'
                'Please go to "E-Commerce Integrations → Stores → %s → Quick Configuration wizard" '
                'and set the "Integration Language".'
            ) % (self.name, self.name))

        code = lang.code

        if not self.env['res.lang']._lang_get(code):
            raise UserError(_(
                '%s: The language "%s" is inactive or not available in Odoo.\n\n'
                'Please ensure that the language is active in the system settings by going to '
                '"Settings → Translations → Languages".'
            ) % (self.name, code))

        return code

    def get_shop_lang_code(self):
        """
        Return language code like `en_US` based on the `lang` adapter property
        with essential conditions: required=True, active=True
        """
        lang = self._get_shop_lang()
        return lang.code

    def get_adapter_lang_code(self):
        """
        Return language code like the `mapping-formatted` code:
            '1', 'en', 'eng', 'Eng', 'en_EN', etc.
        """
        return self.adapter.lang

    def _get_shop_lang(self, raise_error=True):
        external_language_code = self.get_adapter_lang_code()

        lang = self.env['res.lang'].from_external(
            self,
            external_language_code,
            raise_error=raise_error,
        )

        if raise_error:
            assert lang.active, f'Inactive language: {lang.code}'

        return lang

    def import_stock_levels_integration(self, location_line):
        self.ensure_one()

        idx = int()
        adapter = self.adapter
        limit = self.get_external_block_limit()

        location = location_line.erp_location_id
        external_location_code = location_line.external_location_id.code

        stock_levels_data = adapter.get_stock_levels(external_location_code)
        stock_levels = [(key, value) for key, value in stock_levels_data.items()]

        context = {
            'company_id': self.company_id.id,
            'job_integration_id': self.id,
            'job_integration_job_type': 'inventory',
        }
        self = self.with_context(**context)

        while stock_levels:
            idx += 1
            job_kwargs = self._job_kwargs_apply_stock_multi(location_line, block=idx)

            self \
                .with_delay(**job_kwargs) \
                .run_apply_stock_levels_by_blocks(stock_levels[:limit], location)

            stock_levels = stock_levels[limit:]

        return True

    def run_apply_stock_levels_by_blocks(self, stock_levels, location):
        for external_code, qty in stock_levels:
            self._integration_apply_stock_qty(location, external_code, qty)
        return location, stock_levels

    def _integration_apply_stock_qty(self, location, external_code, qty, delay=True):
        ProductProductExternal = self.env['integration.product.product.external'].with_context(
            company_id=self.company_id.id,
        )
        external_id = ProductProductExternal.get_external_by_code(
            self,
            external_code,
            raise_error=False,
        )
        if not external_id:
            _logger.warning(
                '%s: import stock levels. Cannot find external record "%s" in ERP',
                self.name,
                external_code,
            )
            return False

        if delay:
            job_kwargs = self._job_kwargs_apply_stock_single(external_code, location)
            context = {
                'company_id': self.company_id.id,
                'job_integration_id': self.id,
                'job_integration_job_type': 'inventory',
            }
            job = external_id\
                .with_context(**context) \
                .with_delay(**job_kwargs) \
                .apply_stock_levels(qty, location)

            external_id.mapping_model.to_odoo(
                self,
                external_code,
                raise_error=False,
            )
        else:
            job = external_id.apply_stock_levels(qty, location)

        return job

    def _get_trackable_fields(self):
        """Get fields that can be updated on external system"""
        field_ids = self.env['product.ecommerce.field.mapping'].search([
            ('active', '=', True),
            ('export_enabled', '=', True),
            ('integration_id', '=', self.id),
        ])
        return field_ids.sudo().trackable_fields_rel

    def _is_need_export_product(self, field_vals):
        """
        :field_vals: dict from product `create` or `write` method
        """
        if not self.is_product_template_export_enabled:
            return False

        self_su = self.sudo()
        changed_fields = self_su.env['ir.model.fields'].sudo().search([
            ('name', 'in', list(field_vals.keys())),
            ('model', 'in', ('product.template', 'product.product')),
        ])

        trackable_fields = self_su._get_trackable_fields()
        trackable_fields |= self_su.global_tracked_fields

        return bool(changed_fields & trackable_fields)

    def _is_need_export_images(self, vals):
        if not (self.is_product_template_export_enabled and self.allow_export_images):
            return False

        return bool(set(IMAGE_FIELDS).intersection(set(vals.keys())))

    def _get_original_from_translations(self, translations):
        """
        Retrieve the original text from a dictionary of translations based on the integration language.

        :param translations: dict containing language keys and their respective translations.
        :return: The original translation in the integration language or the full translation dictionary if not found.
        """
        if not (isinstance(translations, dict) and translations.get('language')):
            return translations

        odoo_lang = self.integration_lang_id

        if odoo_lang.id not in translations['language']:
            raise es.ApiImportError(_(
                'Cannot find the default language with ID "%s" in the list of translations: %s.\n\n'
                'Please ensure that the correct language is configured in the e-commerce system.'
            ) % (odoo_lang.id, list(translations['language'].keys())))

        return translations['language'][odoo_lang.id]

    def _prepare_inventory_data(self, product, locations, ext_product, ext_location_id):
        """
        Prepare inventory data for export.

        :param product: The Odoo product record.
        :param locations: The list of Odoo locations.
        :param ext_product: The external product.
        :param ext_location_id: The external location ID for which inventory data is being prepared.
        :return: A dictionary containing inventory data.
        """

        qty_field = self.synchronise_qty_field
        total_qty = 0  # Default value

        locations = locations.sudo()
        if not self.allow_multi_company_inventory_calculation:
            locations = locations.filtered(lambda loc: loc.company_id == self.company_id)

        # Detect KIT (phantom BOM) products
        is_kit = bool(product.bom_ids.filtered(lambda b: b.type == 'phantom'))

        if self.update_stock_for_manufacture_boms and product.bom_ids and not is_kit:
            # For products with manufacturing BOMs (not kits)
            for loc in locations:
                if self.allow_multi_company_inventory_calculation:
                    company_id = loc.company_id
                    product = product.with_company(company_id)
                # use context for each location
                total_qty += product.with_context(location=loc.id)._compute_qty_producible(qty_field)
            total_qty += getattr(product.with_context(location=locations.ids), qty_field, 0)
        elif hasattr(product, qty_field):
            product = product.with_context(location=locations.ids)
            total_qty = getattr(product, qty_field)
        else:
            raise ValidationError(_(
                'There is no %s field in product.product module to get quantity of '
                'product for inventory export'
            ) % qty_field)

        return {
            'qty': total_qty,
            'external_reference': ext_product.external_reference,
            'external_location_id': ext_location_id,
        }

    def open_import_export_integration_wizard(self):
        """
        Returns action window with 'Import/Export Integration Wizard'
        """
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': _('Import/Export Integration Wizard'),
            'res_model': 'import.export.integration.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('integration.import_export_integration_wizard_form').id,
            'target': 'new',
            'context': self.env.context,

        }

    def get_unmapped_mappings(self):
        """
        Get a list of unmapped mappings with names and counts.

        Returns:
            list: List of dictionaries with 'name', and 'count' keys.
        """
        self.ensure_one()

        unmapped_mappings = []

        # Get all entities for this integration type
        domain = ['|', ('integration_type', '=', False), ('integration_type', '=', self.type_api)]
        entities = self.env['integration.import.entity'].search(domain)

        for entity in entities:
            if not entity.mapping_model:
                continue

            # Get the mapping model
            if entity.mapping_model not in self.env:
                _logger.warning(
                    f'{self.name}: Mapping model "{entity.mapping_model}" not found'
                )
                continue

            # Get the internal field name from the mapping model
            mapping_model = self.env[entity.mapping_model]
            internal_field_name = \
                mapping_model._mapping_fields[0] if hasattr(mapping_model, '_mapping_fields') else None

            if not internal_field_name:
                continue

            # Count unmapped records
            unmapped_count = mapping_model.search_count([
                ('integration_id', '=', self.id),
                (internal_field_name, '=', False),
            ])

            if unmapped_count > 0:
                unmapped_mappings.append({
                    'name': entity.name,
                    'count': unmapped_count,
                    'model_name': entity.mapping_model,
                })

        return unmapped_mappings

    def get_order_url(self, external_order_id):
        """
        Get the order URL for the given external order ID.
        """
        return self.adapter.get_order_url(external_order_id)

    def get_product_url(self, external_product_code):
        """
        Get the product URL for the given external product code.
        """
        self.ensure_one()

        return self.adapter.get_product_url(external_product_code)

    @staticmethod
    def _raise_notification(ttype: str, message: str):
        """
        :ttype:
            - success
            - warning
        """
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': message,
                'type': ttype,
                'sticky': False,
            }
        }

    def _get_input_file(self, external_order_id: str):
        input_file = self.env['sale.integration.input.file'].search([
            ('si_id', '=', self.id),
            ('name', '=', str(external_order_id)),
        ], limit=1)

        if not input_file:
            message = (
                f'{self.name}: Integration Input-file not found '
                f'(external_id={external_order_id})'
            )
            _logger.warning(message)
            return False

        return input_file

    def _get_odoo_product(self, variant_code, raise_error=False):
        product = self.env['product.product'].from_external(
            self,
            variant_code,
            raise_error=False,
        )

        if not product and raise_error:
            raise es.NotMappedFromExternal(
                _(
                    'Failed to find the external product variant with code "%s".\n\n'
                    'To resolve this issue, please run "Link Products" using the button '
                    'on the "Initial Import" tab in your "%s" integration settings.\n'
                    'After that, verify that all products are correctly mapped in the following menus:\n'
                    '1. "Mappings → Products"\n'
                    '2. "Mappings → Product Variants"'
                ) % (variant_code, self.name),
                model_name='integration.product.product.external',
                code=variant_code,
                integration=self,
            )

        return product

    def _try_get_odoo_product(self, product_data, force_create=False):
        """
        Try to find an Odoo product (product.product) by external product code.
        If not found, attempt to re-import from the external system and optionally
        auto-create the product in Odoo.

        :param product_data: dict with product identification data. Expected keys:
            - product_id (str, required): external complex variant code
            - odoo_variant_id (int, optional): known Odoo product.product ID,
              used as shortcut to skip lookup (e.g. for bundle/kit products)
            - name (str, optional): product name, used in error messages
            - reference (str, optional): product reference, used in error messages
        :param force_create: if True, auto-create product even if
            ``auto_create_products_on_so`` is disabled
        :return: product.product recordset
        """
        # If odoo_variant_id is already known, use it directly. This happens during order import
        # with bundle/kit products, where the connector resolves (or creates) the Kit product
        # during bundle parsing and stores the resulting product ID in the line data.
        if 'odoo_variant_id' in product_data:
            return self.env['product.product'].browse(product_data['odoo_variant_id'])

        complex_variant_code = product_data['product_id']

        if not complex_variant_code:
            es.raise_error(
                err_code='E109',
                integration_name=self.name,
                product_name=product_data.get('name', 'null'),
                product_reference=product_data.get('reference', 'null'),
            )

        product = self._get_odoo_product(complex_variant_code)
        if product:
            return product

        # If the product is not found, attempt to re-import it from the external system
        template_code, variant_code = self.adapter._parse_product_external_code(complex_variant_code)
        external_template, external_variants, __, __ = self._import_external_product(template_code)

        # Use fallback product if no external templates found or variant code doesn't match.
        if not external_template or complex_variant_code not in external_variants.mapped('code'):
            es.raise_error(
                err_code='E110',
                integration_name=self.name,
                product_id=template_code,
                variant_id=variant_code,
                product_name=product_data.get('name', 'null'),
                product_reference=product_data.get('reference', 'null'),
            )

        auto_create_product = force_create or self.auto_create_products_on_so
        product = self._get_odoo_product(
            complex_variant_code,
            raise_error=(not auto_create_product),
        )

        if auto_create_product and not product:
            # Try to create ERP product on the fly
            external_record = self.env['integration.product.template.external'] \
                .get_external_by_code(self, template_code)

            self.import_product(
                external_record.id,
                import_images=self.allow_import_images,
            )
            product = self._get_odoo_product(complex_variant_code, raise_error=True)

        return product

    def _get_order_sub_status(self, ext_current_state):
        SubStatus = self.env['sale.order.sub.status']

        sub_status = SubStatus.from_external(self, ext_current_state, raise_error=False)

        if not sub_status:
            self.integrationApiImportSaleOrderStatuses()
            sub_status = SubStatus.from_external(self, ext_current_state)

        return sub_status

    def _get_order_sub_status_tuple(self, status_code):
        _name = 'sale.order.sub.status'

        sub_status_id = self.env[_name].from_external(self, status_code, False)
        external_sub_status = self.env[f'integration.{_name}.external'] \
            .get_external_by_code(self, status_code, False)

        if not sub_status_id:
            _logger.error(
                f'{self.name}: Store order status not found (status_code={status_code})'
            )

        return sub_status_id, external_sub_status

    @staticmethod
    def _validate_external_id(external_id):
        """
        Validate the external ID.
        Raises:
            ValidationError: If the external ID is invalid.
        """
        if not external_id:
            _logger.warning(f'Invalid external ID: {external_id}')
            raise ValidationError(f'Invalid external ID: {external_id}.')

        try:
            external_id = int(external_id)

            if external_id <= 0:
                _logger.warning(f'Invalid external ID: {external_id}')
                raise ValidationError(f'Invalid external ID: {external_id}.')

        except (ValueError, TypeError):
            _logger.warning(f'Invalid external ID: {external_id}')
            raise ValidationError(f"Invalid external ID: {external_id}.")

        return external_id

    def _get_external_product(self, external_id):
        """
        Get the external product by ID.
        """
        try:
            self._validate_external_id(external_id)
        except ValidationError:
            return None

        record = self.env['integration.product.template.external'] \
            .get_external_by_code(self, external_id, raise_error=False)

        return record

    def _save_log(self, vals):
        try:
            with Registry(self.env.cr.dbname).cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})
                log = env['integration.logging'].create(vals)
        except Exception:
            _logger.error('Failed to save log')
            log = self.env['integration.logging']

        return log

    def action_open_price_preview(self):
        raise NotImplementedError

    # --- Converters methods ---

    def convert_external_attributes(self, ext_attribute_value_ids):
        ProductAttributeValue = self.env['product.attribute.value']
        attr_values_ids_by_attr_id = defaultdict(list)
        attribute_value_ids = ProductAttributeValue

        for ext_attribute_value_id in ext_attribute_value_ids:
            attribute_value_ids |= ProductAttributeValue.from_external(self, ext_attribute_value_id)

        for attribute_value_id in attribute_value_ids:
            attribute_id = attribute_value_id.attribute_id.id
            attr_values_ids_by_attr_id[attribute_id].append(attribute_value_id.id)

        return attr_values_ids_by_attr_id

    def convert_external_categories(self, ext_category_ids: list) -> list:
        ProductPublicCategory = self.env['ecommerce.product.category']
        odoo_categories = ProductPublicCategory

        for external_category_id in ext_category_ids:
            if external_category_id:
                odoo_categories |= ProductPublicCategory.from_external(self, external_category_id)

        return odoo_categories.ids

    def convert_external_tax(self, tax_value: int) -> list:
        odoo_tax = self._convert_external_tax(tax_value)

        if not odoo_tax:
            raise es.ApiImportError(_(
                'The product cannot be imported into Odoo for the "%s" integration. '
                'The external tax value "%s" could not be converted to a corresponding Odoo tax value. '
                'Please ensure that the external tax values are correctly mapped to Odoo taxes.'
            ) % (self.name, tax_value))

        return odoo_tax

    def _handle_missing_order(
        self,
        external_order_id: str,
        integration_workflow_states: list,
        date_order: str = None,
    ):
        """
        Handle the common logic for checking if an order exists and deciding whether to import it.

        Args:
            integration: The integration instance
            external_order_id: The external order ID
            data: The pipeline data

        Returns:
            tuple: (should_import, response_message) where should_import is a boolean
                   indicating if the order should be imported, and response_message
                   is the response to return if should_import is True
        """
        # Check if orders can be imported
        if not self.is_order_import_enabled:
            message = f'Order import is disabled for self {self.name} or integration is not active.'
            _logger.info(message)
            return False, message

        # Check if order exists in the system
        input_file = self._get_input_file(external_order_id)

        if not input_file:
            # Order doesn't exist, check if it should be imported based on status
            if not self.is_importable_order_status(integration_workflow_states):
                message = f'Order with code={external_order_id} is not in the expected status for import.'
                _logger.info(message)
                return False, message

            # Check cut-off date if configured
            if not self.is_importable_order_date(date_order):
                message = (
                    f'Order with code={external_order_id} was created before the cut-off date '
                    f'({self.orders_cut_off_datetime}). Order creation date: {date_order}.'
                )
                _logger.info(message)
                return False, message

            # Order doesn't exist but status matches import filters, trigger import
            self.fetch_order_by_id_with_delay(external_order_id)
            return True, f'Order import job created for order with code={external_order_id}'

        return None, None  # Order exists, continue with normal processing
