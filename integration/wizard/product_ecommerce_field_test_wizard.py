# See LICENSE file for full copyright and licensing details.

import json
import logging
import traceback

from odoo import api, models, fields, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ProductEcommerceFieldTestWizard(models.TransientModel):
    _name = 'product.ecommerce.field.test.wizard'
    _description = 'Test Field Mapping Wizard'

    # ==================== Core Fields ====================

    ecommerce_field_id = fields.Many2one(
        comodel_name='product.ecommerce.field',
        string='Field Definition',
        required=True,
        readonly=True,
        ondelete='cascade',
    )

    field_name = fields.Char(
        related='ecommerce_field_id.name',
        string='Field',
    )

    type_api = fields.Selection(
        related='ecommerce_field_id.type_api',
        string='Connector Type',
    )

    is_template_field = fields.Boolean(
        related='ecommerce_field_id.is_template_field',
    )

    is_variant_field = fields.Boolean(
        related='ecommerce_field_id.is_variant_field',
    )

    # ==================== Integration Selection ====================

    integration_id = fields.Many2one(
        comodel_name='sale.integration',
        string='Store',
        required=True,
        domain="[('type_api', '=', type_api)]",
        ondelete='cascade',
    )

    mapping_id = fields.Many2one(
        comodel_name='product.ecommerce.field.mapping',
        string='Existing Mapping',
        compute='_compute_mapping_id',
        store=False,
    )

    mapping_exists = fields.Boolean(
        string='Mapping Exists',
        compute='_compute_mapping_id',
        store=False,
    )

    # ==================== Import Test Fields ====================

    external_template_id = fields.Many2one(
        comodel_name='integration.product.template.external',
        string='External Product',
        domain="[('integration_id', '=', integration_id)]",
        ondelete='cascade',
    )

    external_variant_id = fields.Many2one(
        comodel_name='integration.product.product.external',
        string='External Variant',
        domain="[('external_product_template_id', '=', external_template_id)]",
        ondelete='cascade',
    )

    import_result = fields.Text(
        string='Import Result',
        readonly=True,
    )

    import_tested = fields.Boolean(
        string='Import Tested',
        default=False,
    )

    import_success = fields.Boolean(
        string='Import Success',
        default=False,
    )

    # ==================== Export Test Fields ====================

    product_template_id = fields.Many2one(
        comodel_name='product.template',
        string='Odoo Product',
        ondelete='cascade',
    )

    product_variant_id = fields.Many2one(
        comodel_name='product.product',
        string='Odoo Variant',
        domain="[('product_tmpl_id', '=', product_template_id)]",
        ondelete='cascade',
    )

    export_result = fields.Text(
        string='Export Result',
        readonly=True,
    )

    export_tested = fields.Boolean(
        string='Export Tested',
        default=False,
    )

    export_success = fields.Boolean(
        string='Export Success',
        default=False,
    )

    # ==================== Error Handling Fields ====================

    error_message = fields.Text(
        string='Error Message',
        readonly=True,
    )

    error_traceback = fields.Text(
        string='Error Traceback',
        readonly=True,
    )

    has_error = fields.Boolean(
        string='Has Error',
        compute='_compute_has_error',
    )

    # ==================== Computed Fields ====================

    @api.depends('integration_id', 'ecommerce_field_id')
    def _compute_mapping_id(self):
        for rec in self:
            if rec.integration_id and rec.ecommerce_field_id:
                mapping = rec.ecommerce_field_id._get_mapping_for_integration(
                    rec.integration_id.id,
                    mark_active=False,
                )
                rec.mapping_id = mapping
                rec.mapping_exists = bool(mapping)
            else:
                rec.mapping_id = False
                rec.mapping_exists = False

    @api.depends('error_message')
    def _compute_has_error(self):
        for rec in self:
            rec.has_error = bool(rec.error_message)

    # ==================== Onchange Methods ====================

    @api.onchange('integration_id')
    def _onchange_integration_id(self):
        """Clear test data when integration changes."""
        self.external_template_id = False
        self.external_variant_id = False
        self.product_template_id = False
        self.product_variant_id = False
        self._clear_results()

    @api.onchange('external_template_id')
    def _onchange_external_template_id(self):
        """Clear variant and results when template changes."""
        self.external_variant_id = False
        self.import_result = False
        self.import_tested = False
        self.import_success = False
        self._clear_error()

    @api.onchange('product_template_id')
    def _onchange_product_template_id(self):
        """Clear variant and results when template changes."""
        self.product_variant_id = False
        self.export_result = False
        self.export_tested = False
        self.export_success = False
        self._clear_error()

    # ==================== Action Methods ====================

    def action_test_import(self):
        """
        Test import: fetch value from e-commerce and show what would be imported to Odoo.
        Works directly with ecommerce_field_id without requiring a mapping.
        """
        self.ensure_one()
        self._clear_error()

        if not self.integration_id:
            raise UserError(_('Please select a store first.'))

        if not self.external_template_id:
            raise UserError(_('Please select an external product to test import.'))

        if self.is_variant_field and not self.external_variant_id:
            raise UserError(_('This is a variant-level field. Please select an external variant.'))

        try:
            # Fetch product data from external API
            template_data, variant_data = self._fetch_external_product_data()

            # Determine Odoo record if exists (for script context)
            odoo_id = self._get_odoo_record_for_import()

            # Calculate import value directly using ecommerce_field_id
            result = self.ecommerce_field_id.calculate_import_value(
                self.integration_id.id,
                (template_data, variant_data),
                odoo_id,
            )

            self.write({
                'import_result': self._format_result(result),
                'import_tested': True,
                'import_success': True,
            })

        except Exception as e:
            _logger.exception('Error during import test')
            self.write({
                'import_result': False,
                'import_tested': True,
                'import_success': False,
                'error_message': str(e),
                'error_traceback': traceback.format_exc(),
            })

        return self._return_wizard()

    def action_test_export(self):
        """
        Test export: read value from Odoo and show what would be sent to e-commerce.
        Works directly with ecommerce_field_id without requiring a mapping.
        """
        self.ensure_one()
        self._clear_error()

        if not self.integration_id:
            raise UserError(_('Please select a store first.'))

        if not self.product_template_id:
            raise UserError(_('Please select an Odoo product to test export.'))

        if self.is_variant_field and not self.product_variant_id:
            raise UserError(_('This is a variant-level field. Please select an Odoo variant.'))

        try:
            # Determine which Odoo ID to use
            if self.is_template_field:
                odoo_id = self.product_template_id.id
            else:
                odoo_id = self.product_variant_id.id

            # Calculate export value directly using ecommerce_field_id
            result = self.ecommerce_field_id.calculate_export_value(
                self.integration_id.id,
                odoo_id,
            )

            self.write({
                'export_result': self._format_result(result),
                'export_tested': True,
                'export_success': True,
            })

        except Exception as e:
            _logger.exception('Error during export test')
            self.write({
                'export_result': False,
                'export_tested': True,
                'export_success': False,
                'error_message': str(e),
                'error_traceback': traceback.format_exc(),
            })

        return self._return_wizard()

    def action_create_mapping(self):
        """
        Create a new mapping for this field and integration.
        """
        self.ensure_one()
        self._clear_error()

        if self.mapping_exists:
            raise UserError(_('Mapping already exists for this field and store.'))

        if not self.integration_id:
            raise UserError(_('Please select a store first.'))

        try:
            self.ecommerce_field_id._ensure_mapping(self.integration_id.id, mark_active=True)
        except Exception as e:
            _logger.exception('Error creating mapping')
            self.write({
                'error_message': str(e),
                'error_traceback': traceback.format_exc(),
            })

        return self._return_wizard()

    def action_clear_error(self):
        """Clear error message and traceback."""
        self.ensure_one()
        self._clear_error()
        return self._return_wizard()

    # ==================== Helper Methods ====================

    def _clear_results(self):
        """Clear all test results."""
        self.import_result = False
        self.export_result = False
        self.import_tested = False
        self.export_tested = False
        self.import_success = False
        self.export_success = False
        self._clear_error()

    def _clear_error(self):
        """Clear error fields."""
        self.error_message = False
        self.error_traceback = False

    def _fetch_external_product_data(self):
        """
        Fetch product data from external e-commerce API.

        :return: Tuple of (template_data, variant_data)
        """
        self.ensure_one()

        external_template_code = self.external_template_id.code

        # Get product data from API
        template_data, variants_list, *__ = self.integration_id.adapter.get_product_for_import(
            external_template_code
        )

        # Find variant data if needed
        variant_data = None
        if self.is_variant_field and self.external_variant_id:
            from ...api.abstract_apiclient import AbsApiClient
            __, variant_code = AbsApiClient._parse_product_external_code(self.external_variant_id.code)

            variant_data = next(
                (v for v in variants_list if str(v['id']) == variant_code),
                None
            )

            if not variant_data:
                raise UserError(_(
                    'Variant data not found in API response. '
                    'The variant may have been deleted from the e-commerce platform.'
                ))

        return template_data, variant_data

    def _get_odoo_record_for_import(self):
        """
        Get existing Odoo record ID for import context (if product was previously imported).

        :return: Odoo record ID or False
        """
        self.ensure_one()

        external_template_code = self.external_template_id.code

        if self.is_template_field:
            odoo_record = self.env['product.template'].from_external(
                self.integration_id,
                str(external_template_code),
                raise_error=False,
            )
        else:
            from ...api.abstract_apiclient import AbsApiClient

            if self.external_variant_id:
                __, variant_code = AbsApiClient._parse_product_external_code(self.external_variant_id.code)
            else:
                variant_code = None

            code = AbsApiClient._build_product_external_code(external_template_code, variant_code)
            odoo_record = self.env['product.product'].from_external(
                self.integration_id,
                code,
                raise_error=False,
            )

        return odoo_record.id if odoo_record else False

    def _format_result(self, result):
        """
        Format the result dictionary for display.
        """
        if isinstance(result, dict):
            try:
                return json.dumps(result, indent=2, ensure_ascii=False, default=str)
            except (TypeError, ValueError):
                return str(result)
        return str(result)

    def _return_wizard(self):
        """
        Return action to keep wizard open after button click.
        """
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
