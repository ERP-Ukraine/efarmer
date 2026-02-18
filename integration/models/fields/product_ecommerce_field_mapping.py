# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import UserError

from ...api.abstract_apiclient import AbsApiClient


class ProductEcommerceFieldMapping(models.Model):
    _name = 'product.ecommerce.field.mapping'
    _description = 'Product Fields Integration Mapping'

    name = fields.Char(
        related='ecommerce_field_id.name',
        readonly=True,
        store=True,
    )

    active = fields.Boolean(
        string='Active',
        default=True,
    )

    integration_id = fields.Many2one(
        comodel_name='sale.integration',
        string='E-CommerceStore',
        required=True,
        ondelete='cascade',
    )

    ecommerce_field_id = fields.Many2one(
        comodel_name='product.ecommerce.field',
        string='Field Definition',
        required=True,
        domain='[("type_api", "=", integration_api_type)]',
        ondelete='cascade',
    )

    integration_api_type = fields.Selection(
        related='integration_id.type_api',
        readonly=True,
        store=True,
    )

    technical_name = fields.Char(
        related='ecommerce_field_id.technical_name',
        readonly=True,
        store=True,
    )

    odoo_model_id = fields.Many2one(
        comodel_name='ir.model',
        related='ecommerce_field_id.odoo_model_id',
        readonly=True,
        store=True,
    )

    odoo_model_name = fields.Char(
        related='ecommerce_field_id.odoo_model_name',
    )

    odoo_field_id = fields.Many2one(
        comodel_name='ir.model.fields',
        related='ecommerce_field_id.odoo_field_id',
        readonly=True,
        store=True,
    )

    odoo_field_name = fields.Char(
        string='Odoo Field (Technical Name)',
        related='ecommerce_field_id.odoo_field_name',
    )

    export_enabled = fields.Boolean(
        string='Export (Odoo → Shop)',
        help='By default fields that are available in the fields mapping will be ALL used '
             'to create new product record on external e-commerce system. But after record '
             'is created, we do not want to mess up and override changes that are done for '
             'that field on external system. Hence we can specify here if that field will be '
             'sent when updating product. ',
    )

    import_enabled = fields.Boolean(
        string='Import (Shop → Odoo)',
        help='By default fields that are available in the fields mapping will be ALL used '
             'to create new product in Odoo. But after record is created, '
             'we do not want to mess up and override changes that are done for '
             'that field in Odoo. Hence we can specify here if that field will be '
             'received when importing product. ',
    )

    trackable_fields_rel = fields.Many2many(
        string='Tracked Fields',
        comodel_name='ir.model.fields',
        related='ecommerce_field_id.trackable_fields_ids',
    )

    is_reference = fields.Boolean(
        string='Reference',
        compute='_compute_advanced_properties',
    )

    is_barcode = fields.Boolean(
        string='Barcode',
        compute='_compute_advanced_properties',
    )

    import_script = fields.Text(
        related='ecommerce_field_id.import_script',
    )

    export_script = fields.Text(
        related='ecommerce_field_id.export_script',
    )

    is_template_field = fields.Boolean(
        related='ecommerce_field_id.is_template_field',
    )

    is_variant_field = fields.Boolean(
        related='ecommerce_field_id.is_variant_field',
    )

    is_translatable_field = fields.Boolean(
        related='ecommerce_field_id.is_translatable_field',
    )

    is_scriptable_field = fields.Boolean(
        related='ecommerce_field_id.is_scriptable_field',
    )

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f'{rec.integration_id.name}: {rec.name}'

    @api.depends('odoo_field_id')
    def _compute_advanced_properties(self):
        for rec in self:
            rec.is_reference = (
                (rec.integration_id.template_reference_id == rec.ecommerce_field_id)
                or (rec.integration_id.product_reference_id == rec.ecommerce_field_id)
            )
            rec.is_barcode = (
                (rec.integration_id.template_barcode_id == rec.ecommerce_field_id)
                or (rec.integration_id.product_barcode_id == rec.ecommerce_field_id)
            )

    @api.onchange('ecommerce_field_id')
    def _onchange_ecommerce_field_id(self):
        self.export_enabled = self.ecommerce_field_id.default_for_update
        self.import_enabled = self.ecommerce_field_id.default_for_import

    def mark_active(self):
        """
        Activate the mapping for synchronization.
        """
        return self.write({'active': True})

    def mark_inactive(self):
        """
        Deactivate the mapping to exclude it from synchronization.
        """
        return self.write({'active': False})

    @api.model_create_multi
    def create(self, vals_list):
        res = super(ProductEcommerceFieldMapping, self).create(vals_list)

        for vals, rec in zip(vals_list, res):
            update_vals = dict()

            if 'export_enabled' not in vals:
                update_vals['export_enabled'] = rec.ecommerce_field_id.default_for_update

            if 'import_enabled' not in vals:
                update_vals['import_enabled'] = rec.ecommerce_field_id.default_for_import

            if update_vals:
                rec.write(update_vals)

        return res

    def get_translatable_template_api_names(self):
        """
        Get API field names for translatable template fields.

        :return: List of technical_name values for translatable template fields
        """
        mappings = self._search_translatable_fields()
        mappings = mappings.filtered(lambda x: x.is_template_field)
        return mappings.mapped(lambda x: x.technical_name)

    def get_translatable_variant_api_names(self):
        """
        Get API field names for translatable variant fields.

        :return: List of technical_name values for translatable variant fields
        """
        mappings = self._search_translatable_fields()
        mappings = mappings.filtered(lambda x: x.is_variant_field)
        return mappings.mapped(lambda x: x.technical_name)

    def get_translatable_template_odoo_names(self):
        """
        Get Odoo field names for translatable template fields.

        :return: List of odoo_field_name values for translatable template fields
        """
        mappings = self._search_translatable_fields()
        mappings = mappings.filtered(lambda x: x.is_template_field)
        return mappings.mapped(lambda x: x.odoo_field_name)

    def _search_translatable_fields(self):
        """
        Search for translatable field mappings, optionally filtered by integration.

        Uses context key 'integration_id' to filter by specific integration.

        :return: Recordset of translatable field mappings
        """
        domain = list()

        integration_id = self.env.context.get('integration_id')
        if integration_id:
            domain.append(('integration_id', '=', integration_id))

        return self.search(domain).filtered(lambda x: x.is_translatable_field)

    def add_mapping_using_another_field(self, type_api, field_list):
        """
        Create mappings for new fields based on existing field mappings.

        Used in migrations when adding new e-commerce fields that should inherit
        settings from existing similar fields.

        :param type_api: API type identifier (e.g., 'shopify', 'woocommerce')
        :param field_list: List of tuples [(new_field_xmlid, old_field_xmlid), ...]
        """
        integrations = self.env['sale.integration'].with_context(active_test=False).search([
            ('type_api', '=', type_api),
        ])

        module_name = 'integration_%s.' % type_api

        for integration in integrations:
            for field in field_list:
                field_new = self.env.ref(module_name + field[0])
                field_old = self.env.ref(module_name + field[1])

                mapping_old = self.search([
                    ('integration_id', '=', integration.id),
                    ('ecommerce_field_id', '=', field_old.id),
                ])

                if mapping_old:
                    self.env['product.ecommerce.field.mapping'].create({
                        'integration_id': integration.id,
                        'ecommerce_field_id': field_new.id,
                        'export_enabled': mapping_old.export_enabled,
                        'import_enabled': mapping_old.import_enabled,
                    })

    # ==================== Import Flow ====================

    def calculate_import_value(self, template_data: dict, variants_data: dict = None, odoo_id: int = None):
        """
        Calculate import value for a product using this mapping's field configuration.

        Delegates to ecommerce_field_id.calculate_import_value() with integration context.

        :param template_data: Product template data from external API
        :param variants_data: Optional variants data from external API
        :param odoo_id: Optional existing Odoo record ID for updates
        :return: Dict with {odoo_field_name: converted_value}
        """
        self.ensure_one()

        return self.ecommerce_field_id.calculate_import_value(
            self.integration_id.id,
            (template_data, variants_data),
            odoo_id,
        )

    def fetch_and_calculate_import_value(self, external_template_id: int, external_variant_id: int = None):
        """
        Fetch product data from external API and calculate import value.

        This method performs an API call to retrieve fresh data from the external
        e-commerce system, then calculates the import value for the field.

        Use this for testing/debugging field mappings or when you need to
        recalculate a single field's value from external source.

        :param external_template_id: Odoo ID for 'integration.product.template.external'
        :param external_variant_id: Optional Odoo ID for 'integration.product.product.external'
        :return: Dict with {odoo_field_name: converted_value}
        """
        external_template = self.env['integration.product.template.external'].browse(external_template_id)

        if external_variant_id:
            external_variant = self.env['integration.product.product.external'].browse(external_variant_id)
            __, variant_code = AbsApiClient._parse_product_external_code(external_variant.code)
        else:
            variant_code = None

        return self._fetch_and_calculate_import_value(external_template.code, variant_code)

    def _fetch_and_calculate_import_value(self, external_template_id: str, external_variant_id: str = None):
        """
        Internal method to fetch and calculate import value using external codes.

        :param external_template_code: E-commerce template ID/code
        :param external_variant_code: Optional e-commerce variant ID/code
        :return: Dict with {odoo_field_name: converted_value}
        :raises UserError: If variant data not found when variant_code is provided
        """
        self.ensure_one()

        integration = self.integration_id
        template_data, variants_list, *__ = integration.adapter.get_product_for_import(external_template_id)

        if external_variant_id:
            variant_data = next(
                filter(lambda x: str(x['id']) == external_variant_id, variants_list),
                None
            )

            if not variant_data:
                raise UserError(_(
                    '%s: No variant data found for product (%s). This is a technical issue '
                    'that requires investigation. Please contact our support team: '
                    'https://support.ventor.tech/'
                ) % (integration.name, f'{external_template_id}-{external_variant_id}'))
        else:
            variant_data = None

        record = self.ecommerce_field_id.get_odoo_record()

        if record.is_template:
            odoo_record = self.env['product.template'] \
                .from_external(integration, str(external_template_id), raise_error=False)
        else:
            code = AbsApiClient._build_product_external_code(external_template_id, external_variant_id)
            odoo_record = self.env['product.product'].from_external(integration, code, raise_error=False)

        return self.calculate_import_value(template_data, variant_data, odoo_record.id)

    # ==================== Export Flow ====================

    def calculate_export_value(self, odoo_id: int):
        """
        Calculate export value for a product using this mapping's field configuration.

        Delegates to ecommerce_field_id.calculate_export_value() with integration context.

        :param odoo_id: Odoo record ID (product.template or product.product)
        :return: Dict with {api_field_name: converted_value}
        """
        self.ensure_one()
        return self.ecommerce_field_id.calculate_export_value(self.integration_id.id, odoo_id)
