# See LICENSE file for full copyright and licensing details.

import logging

from odoo import fields, models, api, _
from odoo.tools import float_is_zero
from odoo.tools.misc import groupby


_logger = logging.getLogger(__name__)


class ProductProduct(models.Model):
    _name = 'product.product'
    _inherit = [  # Order of items is important
        'product.product',
        'integration.product.mixin',
        'integration.model.mixin',
        'integration.image.mixin',
    ]
    _image_name = 'image_variant_1920'
    _image_names = 'integration_variant_image_ids'
    _internal_reference_field = 'default_code'

    integration_variant_image_ids = fields.One2many(
        comodel_name='ecommerce.product.image',
        inverse_name='product_variant_id',
        string='Extra Variant Images',
    )

    variant_extra_price = fields.Float(
        string='Variant Extra Price',
        digits='Product Price',
    )

    integration_ids = fields.Many2many(
        comodel_name='sale.integration',
        relation='sale_integration_product_variant',
        column1='product_id',
        column2='sale_integration_id',
        domain=[('state', '=', 'active')],
        string='E-Commerce Stores',
        copy=False,
        default=lambda self: self._prepare_default_integration_ids(),
        tracking=True,
        help='Allow to select which channel this product should be synchronized to. '
             'By default it syncs to all.',
    )

    integration_mapping_ids = fields.One2many(
        comodel_name='integration.product.product.mapping',
        inverse_name='product_id',
        string='E-Commerce Store Mappings',
    )

    mapping_count = fields.Integer(
        string='Mapping Count',
        compute='_compute_mapping_count',
        help='The number of mappings associated with this variant.',
    )

    def _get_view_postprocessed(self, view, arch, **options):
        # Redefined the standard method to update a form-view architecture
        arch, models_ = super()._get_view_postprocessed(view, arch, **options)

        if view.type == 'form':
            arch = self._exclude_convert_to_webp_option(
                arch,
                '//field[@name="image_1920"] | //field[@name="product_variant_image_ids"]',
            )

        return arch, models_

    @property
    def integration_should_export_inventory(self):
        """Determine if the product should be included in inventory export."""
        return (
            (self.is_consumable_storable or (self.type == 'consu' and bool(self.bom_ids)))
            and not self.exclude_from_synchronization
            and not self.exclude_from_synchronization_stock
        )

    def _compute_mapping_count(self):
        for rec in self:
            rec.mapping_count = len(rec.integration_mapping_ids)

    def _get_tmpl_id_for_log(self):
        return self.product_tmpl_id.id

    def open_related_jobs(self):
        self.ensure_one()
        return self.product_tmpl_id.open_related_jobs()

    @api.model_create_multi
    def create(self, vals_list):
        # We need to avoid calling export separately from template and variant.
        ctx = dict(self.env.context, from_product_product=True, from_product_create=True)
        from_product_template = ctx.pop('from_product_template', False)

        if from_product_template:
            # Apply integrations from parent template
            # instead of invoking the `_prepare_default_integration_ids()` method
            for vals in vals_list:
                template = self.env['product.template'].browse(vals.get('product_tmpl_id'))
                vals['integration_ids'] = template._prepare_integration_ids()

        products = super(ProductProduct, self.with_context(ctx)).create(vals_list)

        # If `from_product_template` flag is True, export will be triggered from parent template.
        if ctx.get('skip_product_export') or from_product_template:
            return products

        # If there are no integrations with "Export Product Template Job Enabled" flag -> exit
        if not self.env['sale.integration'].get_integrations('export_template'):
            return products

        router = {rec.id: vals for rec, vals in zip(products, vals_list)}

        for template, variant_list in groupby(products, key=lambda x: x.product_tmpl_id):
            if not template.product_variant_ids or template.exclude_from_synchronization:
                continue

            vals = dict()
            for variant in variant_list:
                vals.update(router[variant.id])

            template._trigger_export_single_template(vals, first_export=True)

        return products

    def write(self, vals):
        if self.env.context.get('skip_product_export'):
            return super(ProductProduct, self).write(vals)

        # We need to avoid calling export separately from template and variant.
        ctx = dict(self.env.context, from_product_product=True)
        from_product_template = ctx.pop('from_product_template', False)

        result = super(ProductProduct, self.with_context(ctx)).write(vals)

        # If `from_product_template` flag is True, export will be triggered from parent template.
        # If `from_product_create` flag is True, export will be triggered from parent create method.
        if from_product_template or ctx.get('from_product_create'):
            return result

        # If there are no integrations with "Export Product Template Job Enabled" flag -> exit
        if not self.env['sale.integration'].get_integrations('export_template'):
            return result

        for template in self.mapped('product_tmpl_id'):
            if not template.product_variant_ids or template.exclude_from_synchronization:
                continue

            template._trigger_export_single_template(vals)

        return result

    @property
    def image_checksum(self):
        value = super().image_checksum

        if not value:
            # If the `image_variant_1920` field is empty,
            # we need to use the main image of the parent template - `image_1920`
            value = self.product_tmpl_id.image_checksum

        return value

    def get_b64_data(self):
        value = super().get_b64_data()

        if not value:
            # If the `image_variant_1920` field is empty,
            # we need to use the main image of the parent template - `image_1920`
            value = self.product_tmpl_id.get_b64_data()

        return value

    def is_image_from_parent(self):
        return bool(self.image_1920) and not bool(self.image_variant_1920)

    def export_images_to_integration(self):
        return self.product_tmpl_id.export_images_to_integration()

    def change_external_integration_variant(self):
        templates = self.mapped('product_tmpl_id')
        return templates.change_external_integration_template()

    def to_export_format(self, integration):
        self.ensure_one()

        attribute_values = []
        for attribute_value in self.product_template_attribute_value_ids:  # product_template_variant_value_ids
            attr_value = attribute_value.product_attribute_value_id
            if attr_value.exclude_from_synchronization:
                continue

            value = attr_value.to_export_format_or_export(integration)
            attribute_values.append(value)

        external_record = self.to_external_record(integration, raise_error=False)

        result = {
            'id': self.id,
            'odoo_external_id': external_record.id,
            'external_id': external_record.code,
            'attribute_values': attribute_values,
            'reference': getattr(self, integration.product_reference_name),
            'reference_api_field': integration.variant_reference_api_name,
            'fields': self.calculate_export_fields_data(integration.id),
        }

        return result

    def get_bom_parent_templates_recursively(self, visited_variants=None):
        """
        This method recursively find all product templates in which these variants are used as BoM components.
        Returns a list of parent product templates.
        """
        if visited_variants is None:
            visited_variants = self
        else:
            visited_variants += self

        boms = self.env['mrp.bom'].search([
            ('bom_line_ids.product_id', 'in', self.ids),
            ('type', 'in', ['phantom', 'normal']),
        ])

        if not boms:
            return self.env['product.template']

        parent_templates = boms.product_tmpl_id
        child_variants = parent_templates.product_variant_ids - visited_variants
        recursive_templates = child_variants.get_bom_parent_templates_recursively(visited_variants)

        return parent_templates + recursive_templates

    @api.depends('product_template_attribute_value_ids.price_extra', 'variant_extra_price')
    def _compute_product_price_extra(self):
        super(ProductProduct, self)._compute_product_price_extra()

        for product in self:
            product.price_extra += product.variant_extra_price

    def action_force_export_inventory(self):
        integrations = self.env['sale.integration'].search([
            ('state', '=', 'active'),
        ])

        variants = self.filtered(lambda x: x.integration_should_export_inventory)

        for integration in integrations:
            if integration.update_stock_for_manufacture_boms:
                tempates_related_to_components = self.get_bom_parent_templates_recursively(variants)
                variants |= tempates_related_to_components.product_variant_ids
            variants.export_inventory_by_jobs(integration)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Export Stock to Stores'),
                'message': 'Queue Jobs "Export Stock to Stores" are created',
                'type': 'success',
                'sticky': False,
            }
        }

    def export_inventory_by_jobs(self, integration, cron_operation=False):
        integration.ensure_one()

        products = self.filtered(
            lambda x: not x.exclude_from_synchronization and (integration in x.integration_ids)
        )
        if not products:
            _logger.info('%s: export inventory task was skipped for %s', integration.name, self)
            return None

        block_size = int(
            self.env['ir.config_parameter'].sudo().get_param(
                'integration.export_inventory_block_size',
            )
        )

        block = 1
        result = list()
        integration = integration.with_context(company_id=integration.company_id.id)
        product_batches = [products[i:i + block_size] for i in range(0, len(products), block_size)]

        for product_batch in product_batches:

            context = {
                'company_id': integration.company_id.id,
                'job_integration_id': integration.id,
                'job_integration_job_type': 'inventory',
                'job_related_record_model': self._name,
                'job_related_record_ids': [p.id for p in product_batch],
            }
            job = integration.with_context(**context).with_delay(
                priority=13,
                description=f'{integration.name}: Export Stock to Stores ({block})',
            ).export_inventory(product_batch, cron_operation=cron_operation)

            result.append(job)

            block += 1

        return result

    def get_quant_integration_location_domain(self, integration):
        locations = integration.get_integration_location()
        domain_quant_loc, _, _ = self.with_context(location=locations.ids)._get_domain_locations()
        return domain_quant_loc

    def _search_pricelist_items(self, p_ids=None, i_ids=None):
        domain = list()  # There is no filed `active` since Odoo-17

        if i_ids:
            domain.append(('id', 'in', i_ids))
        elif p_ids:
            domain.append(('pricelist_id', 'in', p_ids))

        PricelistItem = self.env['product.pricelist.item']

        # 1.  Just for `0_product_variant` applicable option
        add_domain = [
            ('applied_on', '=', '0_product_variant'),
            ('product_id', '=', self.id),
        ]
        variant_item_ids = PricelistItem.search(
            domain + add_domain,
        )
        return variant_item_ids

    def show_variant_mappings(self):
        """TODO: drop it after 1.17.0 release"""
        return {}

    def _compute_qty_producible(self, qty_field, visited_products=None, depth=0):
        """
        Compute the maximum quantity of the product that can be manufactured based on available stock.

        Important:
        When modifying this method, please don't forget to update _prepare_calculation_qty_with_bom method also

        :param qty_field: String, name of the field containing available quantity.
        :param visited_products: Set of product IDs already visited in the recursion to avoid cycles.
        :param depth: Internal—current recursion depth (for debugging).
        :return: Integer, maximum quantity that can be manufactured.
        """
        self.ensure_one()

        if visited_products is None:
            visited_products = set()

        # Fetch current available quantity with location and company context
        loc_id = self.env.context.get('location')
        company = self.env.company
        context = {'location': loc_id, 'company_id': company.id}

        # Read current available qty for the product in the chosen context.
        product_with_context = self.with_context(**context)
        available_qty = getattr(product_with_context, qty_field, 0.0)

        product_id = self.id
        product_name = self.display_name

        # Detect recursion cycles
        if product_id in visited_products:
            _logger.warning(f'Cycle detected in BOM for product {product_name} (ID {product_id}) at depth {depth}')
            return 0

        visited_products.add(product_id)

        try:
            # Find manufacture BoM with active_test=False to include company-specific BOMs
            # The environment already has the company context, so explicit company_id is redundant but harmless.
            # It's better to rely on the env context set by the caller.
            bom = self.env['mrp.bom'].with_context(location=loc_id)._bom_find(
                products=self,
                company_id=company.id,
                bom_type='normal'
            ).get(self)
            if not bom:
                return available_qty

            # Since we use self, BOM needs to be in the same company context.
            bom = bom.with_company(company)
            min_possible_qty = None

            __, bom_line_data = bom.explode(self.with_company(company), 1.0)

            for bom_line, line_data in bom_line_data:
                component = bom_line.product_id
                component_uom = component.uom_id
                required_component_qty = float(line_data.get('qty', 0.0) or 0.0)

                # Apply context for component based on selected qty_field
                component = component.with_context(**context)
                available_component_qty = getattr(component, qty_field, 0.0)

                # Skip service components and consumables without BOMs
                if component.type == 'service' or \
                        (component.type == 'consu' and not component.is_storable and not component.bom_ids):
                    continue

                # Recursively compute available quantity if the component has a BOM
                if component.bom_ids and component.type in ('consu', 'product'):
                    producible_from_bom = component._compute_qty_producible(
                        qty_field, visited_products=visited_products, depth=depth + 1,
                    ) or 0.0
                    # Add producible quantity from BOM to available quantity
                    available_component_qty += producible_from_bom

                # Skip components with zero required quantity — they do not constrain production
                if float_is_zero(required_component_qty, precision_digits=6):
                    continue

                # If available_component_qty is 0 or less, we can't produce anything with this component
                is_available_zero = float_is_zero(available_component_qty, precision_rounding=component_uom.rounding)
                if is_available_zero or available_component_qty <= 0:
                    min_possible_qty = 0
                    break

                # If the UoM of the component is different from the product's UoM, convert the quantity
                if bom_line.product_uom_id != component.uom_id:
                    available_component_qty = component.uom_id._compute_quantity(
                        available_component_qty, bom_line.product_uom_id
                    )

                # Calculate how many batches we can make from this component
                possible_bom_batches = available_component_qty // required_component_qty

                if min_possible_qty is None:
                    min_possible_qty = possible_bom_batches
                else:
                    min_possible_qty = min(min_possible_qty, possible_bom_batches)

            if min_possible_qty:
                # Calculate the maximum quantity based on the number of BoMs that can be produced
                min_possible_qty = min_possible_qty * bom.product_qty

                # If the UoM of the product is different from the BoM's UoM, convert the quantity
                if (
                    min_possible_qty
                    and self.uom_id != bom.product_uom_id
                ):
                    min_possible_qty = bom.product_uom_id._compute_quantity(
                        min_possible_qty, self.uom_id
                    )
            total_producible = min_possible_qty or 0
            _logger.info(f'Computed producible quantity for {product_name}: {total_producible}')

            return total_producible

        finally:
            # Clean up the visited products to avoid affecting siblings at the same depth
            visited_products.remove(product_id)
