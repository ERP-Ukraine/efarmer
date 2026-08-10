import json

from odoo import models, fields, _
from odoo.exceptions import UserError


FIELDS_TO_EXPORT = [
    'name', 'type_api', 'state',
    # The list of fields below is not complete. We export ONLY plain scalar configuration
    # fields (Boolean / Selection / Char / Datetime). We intentionally skip:
    # - relational fields (x2many / x2one): record ids are not portable across instances
    #   and would error or mis-link on import;
    # - computed / related fields: not writable / not meaningful to restore;
    # - automation enablers (cron `*_active`, `*_job_enabled`): would silently start
    #   importing/exporting on the restored copy;
    # - behavior-sync toggles (status push back to the store, auto-apply external
    #   fulfillments/payments) and debug fields (test_method*, force_full_fulfillment):
    #   excluded to guarantee the restored connection has no side effects.
    # ** Please be careful when adding new fields to this list! **
    # Orders import / sync timestamps
    'last_receive_orders_datetime', 'orders_cut_off_datetime',
    'last_order_sync_datetime', 'last_update_pricelist_items',
    'use_order_total_difference_correction', 'use_odoo_so_numbering', 'order_name_ref',
    # Auto-create on order import
    'auto_create_products_on_so', 'auto_create_taxes_on_so',
    'auto_create_delivery_carrier_on_so',
    # Customer mapping
    'use_manual_customer_mapping', 'emails_for_failed_mapping_notifications',
    'skip_individual_contacts', 'use_vat_only_company_search',
    'use_search_customer_fields_ids', 'ignore_vat_validation',
    # Product export / images / pricing
    'allow_import_images', 'allow_export_images', 'send_inactive_product',
    'select_send_sale_price', 'price_including_taxes', 'pricelist_integration',
    'validate_barcode', 'is_import_dynamic_attribute', 'synchronise_qty_field',
    'change_advanced_fields', 'apply_company_on_product',
    'update_stock_for_manufacture_boms', 'ignore_boms_for_product_export',
    # Discounts / bundles
    'separate_discount_line', 'multiple_discount_lines', 'product_bundle_policy',
    # Taxes / invoicing
    'behavior_on_empty_tax', 'behavior_on_non_existing_invoice',
    'update_fiscal_position', 'default_tax_scope',
    # Salesperson / logging
    'keep_sales_person_empty', 'save_log',
]


class ImportExportIntegrationWizard(models.TransientModel):
    _name = 'import.export.integration.wizard'
    _description = 'Import/Export Integration Wizard'

    integration_id = fields.Many2one(
        comodel_name='sale.integration',
        string='E-Commerce Store',
        default=lambda self: self.env.context.get('active_id'),
    )

    state = fields.Selection(
        selection=[
            ('start', 'Start'),
            ('import', 'Import'),
            ('export', 'Export'),
            ('finish', 'Finish'),
        ],
        string='Current Step',
        default='start',
        readonly=True
    )

    input = fields.Text('Input Integration Data')
    output = fields.Text('Output Integration Data')
    message = fields.Text('Message')

    def action_import(self):
        self.state = 'import'

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_export(self):
        self.state = 'export'

        data = {field: getattr(self.integration_id, field) for field in FIELDS_TO_EXPORT}

        # Serialize fields
        data['fields'] = self.integration_id.field_ids.to_dictionary()

        self.output = json.dumps(data, indent=4, default=str)

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def import_data(self):
        """
        Import data from provided JSON input. This will replace all existing parameters
        and fields of the current integration.
        """
        if not self.input:
            raise UserError(_(
                'No data to import.\n\n'
                'Please upload a JSON file containing the integration data before proceeding.'
            ))

        try:
            data = json.loads(self.input)
        except json.JSONDecodeError:
            raise UserError(_(
                'Invalid JSON data.\n\n'
                'Please ensure the uploaded file contains valid JSON and try again.'
            ))

        if data.get('type_api') != self.integration_id.type_api:
            raise UserError(_(
                'The integration type from the uploaded data ("%s") does not match the current integration type.\n\n'
                'Please ensure you are importing data to the correct integration. Expected integration type: "%s".'
            ) % (data.get('type_api'), self.integration_id.type_api))

        for field in FIELDS_TO_EXPORT:
            if field in data:
                setattr(self.integration_id, field, data[field])

        fields = data.get('fields', {})

        self.integration_id.field_ids.unlink()

        fields_data = []
        for field in fields.values():
            field['sia_id'] = self.integration_id.id
            fields_data.append(field)

        self.env['sale.integration.api.field'].create(fields_data)

        self.message = _('Data imported successfully.')
        self.state = 'finish'

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
