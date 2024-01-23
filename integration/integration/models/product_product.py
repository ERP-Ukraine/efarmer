# See LICENSE file for full copyright and licensing details.

import logging

from odoo import fields, models, api, _
from odoo.tools.misc import groupby


_logger = logging.getLogger(__name__)


class ProductProduct(models.Model):
    _name = 'product.product'
    _inherit = ['product.product', 'integration.model.mixin', 'mapping.any.mixin']
    _internal_reference_field = 'default_code'

    product_variant_image_ids = fields.One2many(
        comodel_name='product.image',
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
        string='Sales Integrations',
        copy=False,
        default=lambda self: self._prepare_default_integration_ids(),
        help='Allow to select which channel this product should be synchronized to. '
             'By default it syncs to all.',
    )

    def _get_tmpl_id_for_log(self):
        return self.product_tmpl_id.id

    def open_job_logs(self):
        self.ensure_one()
        return self.product_tmpl_id.open_job_logs()

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

    def export_images_to_integration(self):
        return self.product_tmpl_id.export_images_to_integration()

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        form_data = super().fields_view_get(
            view_id=view_id,
            view_type=view_type,
            toolbar=toolbar,
            submenu=submenu,
        )

        if view_type == 'search':
            form_data = self._update_variant_form_architecture(form_data)

        return form_data

    def change_external_integration_variant(self):
        templates = self.mapped('product_tmpl_id')
        return templates.change_external_integration_template()

    def init_variant_export_converter(self, integration):
        assert len(self) <= 1, 'Recordset is not allowed.'
        integration.ensure_one()
        converter = integration.init_send_field_converter(self)
        return converter

    def to_export_format(self, integration):
        converter = self.init_variant_export_converter(integration)
        return converter.convert_to_external()

    def get_used_in_kits_recursively(self, product_seen=None):
        if product_seen is None:
            product_seen = self
        else:
            product_seen += self
        tmpl = self.env['product.template']

        if not self.mrp_enabled:
            return tmpl

        kits = self.env['mrp.bom'].search([
            ('bom_line_ids.product_id', 'in', self.ids),
            ('type', '=', 'phantom'),
        ])

        if not kits:
            return tmpl

        return (
            kits.product_tmpl_id
            + (kits.product_tmpl_id.product_variant_ids - product_seen).
            get_used_in_kits_recursively(product_seen)
        )

    @api.depends('product_template_attribute_value_ids.price_extra', 'variant_extra_price')
    def _compute_product_price_extra(self):
        super(ProductProduct, self)._compute_product_price_extra()

        for product in self:
            product.price_extra += product.variant_extra_price

    def _variant_ecommerce_field_domain(self, integration, external_code):
        search_domain = [
            ('integration_id', '=', integration.id),
            ('odoo_model_id', '=', self.env.ref('product.model_product_product').id),
        ]
        if external_code:
            search_domain.append(('send_on_update', '=', True))

        return search_domain

    def _update_variant_form_architecture(self, form_data):
        return self.product_tmpl_id._update_template_form_architecture(form_data)

    def action_force_export_inventory(self):
        integrations = self.env['sale.integration'].search([
            ('state', '=', 'active'),
        ])

        variants = self.filtered(
            lambda x: x.type == 'product'
            and not x.exclude_from_synchronization
            and not x.exclude_from_synchronization_stock
        )

        for integration in integrations:
            variants.export_inventory_by_jobs(integration)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Export Product Quantities to External'),
                'message': 'Queue Jobs "Export Product Quantities to External" are created',
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
            job_kwargs = integration._job_kwargs_export_stock_multi(block)

            job = integration.with_delay(**job_kwargs)\
                .export_inventory(product_batch, cron_operation=cron_operation)

            integration.job_log(job)
            result.append(job)

            block += 1

        return result

    def get_quant_integration_location_domain(self, integration):
        locations = integration.get_integration_location()
        domain_quant_loc, _, _ = self.with_context(location=locations.ids)._get_domain_locations()
        return domain_quant_loc

    def get_integration_extra_price(self, integration):
        self.ensure_one()
        price = self.variant_extra_price
        return self.calculate_price_depend_tax(price, integration)

    def get_integration_lst_price(self, integration):
        self.ensure_one()
        price = self.lst_price
        return self.calculate_price_depend_tax(price, integration)

    def _search_pricelist_items(self, p_ids=None, i_ids=None):
        domain = [
            ('active', '=', True),
        ]

        if i_ids:
            domain.append(('id', 'in', i_ids))
        elif p_ids:
            domain.append(('pricelist_id', 'in', p_ids))

        PricelistItem = self.env['product.pricelist.item']

        # 1.  Just for `0_product_variant` applicable option
        add_domain = [
            ('applied_on', '=', '0_product_variant'),
            ('product_id', '=', self.id),
            ('product_tmpl_id', '=', self.product_tmpl_id.id),
        ]
        variant_item_ids = PricelistItem.search(
            domain + add_domain,
        )
        return variant_item_ids
