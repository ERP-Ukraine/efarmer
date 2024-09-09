# See LICENSE file for full copyright and licensing details.

import itertools
from functools import reduce
import logging
from lxml import etree

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

from ..tools import _guess_mimetype, escape_trash
from ..models.sale_integration import EXPORT_EXTERNAL_BLOCK


_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _name = 'product.template'
    _inherit = ['product.template', 'integration.model.mixin', 'mapping.any.mixin']
    _description = 'Product Template'
    _internal_reference_field = 'default_code'

    default_public_categ_id = fields.Many2one(
        comodel_name='product.public.category',
        string='Default Category',
    )

    public_categ_ids = fields.Many2many(
        comodel_name='product.public.category',
        relation='product_public_category_product_template_rel',
        string='Website Product Category',
    )

    public_filter_categ_ids = fields.Many2many(
        comodel_name='product.public.category',
        compute='_compute_public_filter_categories',
        string='Website Product Category Filter',
    )

    product_template_image_ids = fields.One2many(
        comodel_name='product.image',
        inverse_name='product_tmpl_id',
        string='Extra Product Media',
        copy=True,
    )

    website_product_name = fields.Char(
        string='Product Name',
        translate=True,
        help='Sometimes it is required to define separate field with beautiful product name. '
             'And standard field to use for technical name in Odoo WMS (usable for Warehouses). '
             'If current field is not empty it will be used for sending to '
             'e-Commerce System instead of standard field.'
    )

    website_description = fields.Html(
        string='Website Description',
        sanitize=False,
        translate=True,
    )

    website_short_description = fields.Html(
        string='Short Description',
        sanitize=False,
        translate=True,
    )

    website_seo_metatitle = fields.Char(
        string='Meta title',
        translate=True,
    )

    website_seo_description = fields.Char(
        string='Meta description',
        translate=True,
    )

    feature_line_ids = fields.One2many(
        comodel_name='product.template.feature.line',
        string='Product Features',
        inverse_name='product_tmpl_id',
    )

    optional_product_ids = fields.Many2many(
        'product.template', 'product_optional_rel', 'src_id', 'dest_id',
        string='Optional Products', check_company=True)

    to_force_sync_pricelist = fields.Boolean(
        string='Force Update Pricelists',
        help='Export specific prices of the product even if the are no pricelist items. '
        'It means specific prices in external system will be deleted or fully updated.',
    )

    exclude_from_synchronization = fields.Boolean(
        string='Exclude from Synchronization',
        help='Exclude from synchronization with external systems. '
             'It means that product will not be exported to external systems.',
    )

    exclude_from_synchronization_stock = fields.Boolean(
        string='Exclude from Stock Synchronization',
        help='Exclude from stock synchronization with external systems.',
    )

    is_used_dynamic_attributes = fields.Boolean(
        string='Used Dynamic Attributes',
        compute='_compute_used_dynamic_attributes',
        help='Indicates whether the product has any dynamic attributes.',
    )

    mapping_count = fields.Integer(
        string='Mapping Count',
        compute='_compute_mapping_count',
        help=(
            'The number of mappings associated with this product.'
        ),
    )

    def _compute_mapping_count(self):
        TemplateMapping = self.env['integration.product.template.mapping']

        for template in self:
            template.mapping_count = TemplateMapping.search_count([
                ('template_id', '=', template.id),
            ])

    @api.depends('attribute_line_ids')
    def _compute_used_dynamic_attributes(self):
        for template in self:
            all_lines = template.valid_product_template_attribute_line_ids
            lines_without_no_variant = all_lines._without_no_variant_attributes()
            lines = lines_without_no_variant.filtered(lambda l: len(l.value_ids) != 1)

            combination_count = 0
            value_count = [len(x.value_ids) for x in lines]
            if value_count:
                combination_count = reduce(lambda a, b: a * b, value_count)
            variant_count = len(template.with_context(active_test=False).product_variant_ids)
            need_create_variants = combination_count > variant_count
            template.is_used_dynamic_attributes = template.has_dynamic_attributes() and \
                need_create_variants

    def _get_tmpl_id_for_log(self):
        return self.id

    def _export_inventory_on_template(self, integration):
        self.ensure_one()
        integration.ensure_one()

        if self.exclude_from_synchronization:
            return None

        variants = self.product_variant_ids.filtered(lambda x: integration in x.integration_ids)
        if not variants:
            _logger.info('%s: export inventory task was skipped for %s', integration.name, self)
            return None

        result = list()
        integration = integration.with_context(company_id=integration.company_id.id)

        for variant in variants:
            job_kwargs = integration._job_kwargs_export_inventory_variant(variant, False)
            job = integration.with_delay(**job_kwargs).export_inventory_for_variant_job(variant)

            variant.job_log(job)
            result.append(job)

        return result

    def open_job_logs(self):
        self.ensure_one()
        job_log_ids = self.env['job.log'].search([
            ('template_id', '=', self.id),
        ])
        return job_log_ids.open_tree_view()

    def _unmark_force_sync_pricelist(self, ids=False):
        unlink_ids = ids or self.ids
        if not unlink_ids:
            return False

        query = 'UPDATE %s SET to_force_sync_pricelist = false WHERE id IN %%s' % self._table
        params = (tuple(unlink_ids),)

        self.env.cr.execute(query, params)
        return True

    def _search_integrations(self, operator, value):
        if operator not in ('in', '!=', '='):
            return []

        search_value = value
        # Allow setting non-realistic value just to allow adding additional
        # search criteria
        if type(value) is int and value < 0 and operator in ('!=', '='):
            search_value = False
        variants = self.env['product.product'].search([
            ('integration_ids', operator, search_value),
        ])

        template_ids = variants.mapped('product_tmpl_id').ids
        # This is a trick for the search criteria when we want to find product templates
        # where ALL variants do not have ANY integration set ('integration_ids', '=', False)
        # OR find product templates where ALL variants have some integrations set
        # ('integration_ids', '!=', False)
        # OR find all products where some products are without integrations and some with
        # ('integration_ids', '=', -1)
        if search_value is False and operator in ('!=', '='):
            alternative_operator = '='
            if '=' == operator:
                alternative_operator = '!='
            alt_template_ids = self.env['product.product'].search([
                ('integration_ids', alternative_operator, search_value),
            ]).mapped('product_tmpl_id').ids
            if type(value) is int and value < 0:
                # This is special case to have intersections between 2 sets
                # So we find templates that both have variants with and without integrations
                template_ids = list(set(template_ids) & set(alt_template_ids))
            else:
                # Now we need to find difference between found templates
                # And templates that our found with opposite criteria
                template_ids = list(set(template_ids) - set(alt_template_ids))

        return [('id', 'in', template_ids)]

    integration_ids = fields.Many2many(
        comodel_name='sale.integration',
        relation='sale_integration_product',
        column1='product_id',
        column2='sale_integration_id',
        compute='_compute_integration_ids',
        inverse='_inverse_integration_ids',
        domain=[('state', '=', 'active')],
        search=_search_integrations,
        string='Sales Integrations',
        default=lambda self: self._prepare_default_integration_ids(),
        help='Allow to select which channel this product should be synchronized to. '
             'By default it syncs to all.',
    )

    @api.depends('product_variant_ids', 'product_variant_ids.integration_ids')
    def _compute_integration_ids(self):
        for template in self:
            integration_ids = []

            if len(template.product_variant_ids) == 1:
                integration_ids = template.product_variant_ids.integration_ids.ids

            template.integration_ids = [(6, 0, integration_ids)]

    def _inverse_integration_ids(self):
        # TODO: Handle the case when the template has no variants
        for template in self:
            if len(template.product_variant_ids) == 1:
                integration_ids = template.integration_ids.ids
                template.product_variant_ids.integration_ids = [(6, 0, integration_ids)]

    @api.depends('public_categ_ids')
    def _compute_public_filter_categories(self):
        for rec in self:
            category_ids = list()
            rec_categories = rec.public_categ_ids

            if not rec_categories:
                category_ids = rec_categories.search([]).ids
            else:
                for category in rec_categories:
                    category_ids.extend(
                        category.parse_parent_recursively()
                    )

            rec.public_filter_categ_ids = [(6, 0, category_ids)]

    @api.model_create_multi
    def create(self, vals_list):
        # We need to avoid calling export separately from template and variant.
        ctx = dict(self.env.context, from_product_template=True, from_product_create=True)
        from_product_product = ctx.pop('from_product_product', False)

        templates = super(ProductTemplate, self.with_context(ctx)).create(vals_list)

        for template, vals in zip(templates, vals_list):
            # If template has multiple variants, then we need to set `integration_ids`
            # to the all variants after the template is saved and all variants are created.
            if 'integration_ids' in vals:
                if len(template.product_variant_ids) > 1:
                    template.product_variant_ids.integration_ids = vals['integration_ids']

        # If `from_product_product` flag is True, export will be triggered from it's variant.
        if ctx.get('skip_product_export') or from_product_product:
            return templates

        # If there are no integrations with "Export Product Template Job Enabled" flag -> exit
        if not self.env['sale.integration'].get_integrations('export_template'):
            return templates

        for template, vals in zip(templates, vals_list):
            if not template.product_variant_ids or template.exclude_from_synchronization:
                continue

            template._trigger_export_single_template(vals, first_export=True)

        return templates

    def write(self, vals):
        if self.env.context.get('skip_product_export'):
            return super(ProductTemplate, self).write(vals)

        # We need to avoid calling export separately from template and variant.
        ctx = dict(self.env.context, from_product_template=True)
        from_product_product = ctx.pop('from_product_product', False)

        result = super(ProductTemplate, self.with_context(ctx)).write(vals)

        # If `from_product_product` flag is True, export will be triggered from it's variant.
        # If `from_product_create` flag is True, export will be triggered from parent create method.
        if from_product_product or ctx.get('from_product_create'):
            return result

        # If there are no integrations with "Export Product Template Job Enabled" flag -> exit
        if not self.env['sale.integration'].get_integrations('export_template'):
            return result

        if 'active' in vals and not vals['active']:  # TODO: What about the same feature on variant?
            self = self.with_context(active_test=False)

        for template in self:
            if not template.product_variant_ids or template.exclude_from_synchronization:
                continue

            template._trigger_export_single_template(vals)

        return result

    def _trigger_export_single_template(self, vals: dict, first_export: bool = False):
        result = list()

        for integration in self._get_enabled_integrations():
            export_template = first_export or integration._is_need_export_product(vals)
            export_images = integration._is_need_export_images(vals)
            integration = integration.with_context(company_id=integration.company_id.id)

            job = log = None
            # A. Export template + images
            if export_template:
                kw = integration._job_kwargs_export_template(self, export_images)
                job = integration.with_delay(**kw) \
                    .export_template(self, export_images=export_images, make_validation=True)

            # B. Export only images
            elif export_images:
                kw = integration._job_kwargs_export_images(self)
                job = integration.with_delay(**kw).export_images_job(self)

            if job:
                log = self.with_context(default_integration_id=integration.id).job_log(job)

            result.append((integration, log))

        _logger.info('%s: Integration export jobs: %s', self, result)

        return result

    def _get_enabled_integrations(self):
        self.ensure_one()

        integrations = self.mapped('product_variant_ids.integration_ids').filtered(
            lambda x: x.is_active and x.job_enabled('export_template')
        )

        if self.company_id:
            integrations = integrations.filtered(lambda x: x.company_id == self.company_id)

        return integrations

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        form_data = super().fields_view_get(
            view_id=view_id,
            view_type=view_type,
            toolbar=toolbar,
            submenu=submenu,
        )

        if view_type == 'search':
            form_data = self._update_template_form_architecture(form_data)

        return form_data

    @api.onchange('public_categ_ids')
    def _onchange_public_categ_ids(self):
        category_ids = list()

        for category in self.public_categ_ids:
            category_ids.extend(
                category._origin.parse_parent_recursively()
            )

        category_id = self.default_public_categ_id.id
        if category_id and category_ids and category_id not in category_ids:
            self.default_public_categ_id = False

    def change_external_integration_template(self):
        message_pattern = self._get_change_external_message()
        active_ids = self.env.context.get('active_ids')
        active_model = self.env.context.get('active_model')
        message = message_pattern % len(active_ids)

        if active_model == self._name:  # Convert templates to variants
            variants = self.browse(active_ids).mapped('product_variant_ids')

            active_ids = variants.ids
            active_model = variants._name

        context = {
            'active_ids': active_ids,
            'active_model': active_model,
            'default_message': message,
        }

        return {
            'name': _('Change External Integration'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'external.integration.wizard',
            'target': 'new',
            'context': context,
        }

    @staticmethod
    def _get_change_external_message():
        return _(
            'Totally %s products are selected. You can define if selected products will'
            'be synchronised to specific sales integration. Sales Integrations only in "Active"'
            'state are displayed below. Note that you can define this also on'
            '"e-Commerce Integration" tab of every product/product variant individually.'
        )

    def export_images_to_integration(self):
        self.ensure_one()
        integrations = self.mapped('product_variant_ids.integration_ids').filtered(
            lambda x: x.is_active and x.allow_export_images
        )
        for integration in integrations:
            kw = integration._job_kwargs_export_images(self)

            job = integration.with_context(company_id=integration.company_id.id)\
                .with_delay(**kw).export_images_job(self)

            self.with_context(default_integration_id=integration.id).job_log(job)

        return True

    def trigger_export(self, export_images=False, force_integrations=None):
        if self.env.context.get('skip_product_export'):
            _logger.info(
                'Integration export template: %s. Job skipped from context variable.',
                self,
            )
            return

        # The `manual_trigger` flag have to be boolean (not None or something).
        # It used in the `queue.job` identity key formatting.
        manual_trigger = self.env.context.get('manual_trigger', False) or False

        # If len(self) more then EXPORT_EXTERNAL_BLOCK we have do export by batch
        use_jobs_for_blocks, block = len(self) > EXPORT_EXTERNAL_BLOCK, int()

        # Use integrations from the `force_integrations` parameter or find all active integrations
        # with `export_template` flag or without them (if it was force trigger / manual_trigger).
        # Further the `integrations` variable will be filtered for each template separatly
        # according to their `company_id` and related `integration_ids` from variants.
        if not force_integrations:
            # If `manual_trigger` flag is set, no need to check `export_template_job_enabled` flag
            integrations = self.env['sale.integration'].get_integrations(
                False if manual_trigger else 'export_template',
            )
        else:
            integrations = force_integrations

        if not integrations:
            _logger.info('Integration `trigger_export` skipped. There are no active integrations.')
            return

        templates = self
        while templates:
            block += 1
            templates_block = templates[:EXPORT_EXTERNAL_BLOCK]

            if use_jobs_for_blocks:
                templates_block = templates_block.with_delay(  # TODO: undefined company_id in context
                    description=f'Export Templates. Prepare Templates ({block})',
                    priority=20,
                )

            job = templates_block.trigger_export_by_block(
                export_images, integrations, manual_trigger,
            )

            if use_jobs_for_blocks:
                for integration in integrations:
                    integration.job_log(job)

            templates = templates[EXPORT_EXTERNAL_BLOCK:]

    def trigger_export_by_block(self, export_images, integrations, force_trigger):

        for template in self:
            if force_trigger and not template.active:
                template = template.with_context(active_test=False)

            if not template.product_variant_ids or template.exclude_from_synchronization:
                _logger.info(
                    'Integration export template: %s is excluded from synchronization.',
                    template,
                )
                continue

            # Additional filtering integrations if template belong specific company
            if template.company_id:
                integrations = integrations.filtered(lambda x: x.company_id == template.company_id)

            variant_integrations = template.product_variant_ids.mapped('integration_ids')
            enabled_integrations = integrations.filtered(lambda x: x in variant_integrations)

            if not enabled_integrations:
                _logger.info(
                    '%s: Integration `trigger_export` skipped. There are no enabled integrations.',
                    template,
                )

            for integration in enabled_integrations:
                kwargs = dict(export_images=export_images, force=force_trigger)

                is_valid, message = template.validate_in_odoo(integration)
                if not is_valid:
                    kwargs['make_validation'] = True
                    _logger.info(message)

                job_kwargs = integration._job_kwargs_export_template(
                    template, export_images, force=force_trigger,
                )
                job = integration.with_context(company_id=integration.company_id.id)\
                    .with_delay(**job_kwargs).export_template(template, **kwargs)

                template.with_context(default_integration_id=integration.id).job_log(job)

    def _check_filling_mandatory_fields(self, integration):
        variant_ids = self.product_variant_ids
        mandatory_fields = integration.sudo().mandatory_fields_initial_product_export

        for field_name in mandatory_fields.mapped('name'):
            if not all(variant[field_name] for variant in variant_ids):
                message = _('Product Template "%s" (or some of it\'s variants) do not have '
                            'mandatory field "%s" defined.') % (self.display_name, field_name)
                return False, message

        return True, ''

    def validate_in_odoo(self, integration, raise_error=False):

        def not_valid(message):
            if raise_error:
                raise UserError(message)
            return False, message

        # 1. Check mandatory fields
        template_mapping = self.try_to_external(integration)
        if not template_mapping:
            is_valid, message = self._check_filling_mandatory_fields(integration)
            if not is_valid:
                return not_valid(message)

        # 2. Check Internal-references
        ref_field = integration.product_reference_name
        ref_field_count = f'{ref_field}_count'
        internal_references = self.product_variant_ids.filtered(
            lambda x: integration.id in x.integration_ids.ids
        ).mapped(ref_field)

        if not all(internal_references):
            message = _(
                'Product Template "%s" (or some of it\'s variants) do not have '
                'Internal Reference defined. This field is mandatory for the integration '
                'as it is used for automatic mapping') % self.name
            return not_valid(message)

        # 2.1 We also should check if product do not have duplicated internal reference
        # As in Odoo standard duplicated reference is allowed
        # But we do not want to have it in external e-Commerce System
        grouped_products = self.env['product.product'].read_group(
            [
                (ref_field, 'in', internal_references),
                ('product_tmpl_id.exclude_from_synchronization', '=', False)
            ],
            [ref_field],
            [ref_field],
        )

        duplicated_refs = [
            x[ref_field] for x in grouped_products if x[ref_field_count] > 1
        ]
        if duplicated_refs:
            message = _(
                'Multiple products found with the same internal reference(s): %s'
                % ', '.join(duplicated_refs)
            )
            return not_valid(message)

        return True, ''

    def init_template_export_converter(self, integration):
        integration.ensure_one()

        if not self.active:
            self = self.with_context(active_test=False)

        convertor = integration.init_send_field_converter(self)
        return convertor

    def to_export_format(self, integration):
        converter = self.init_template_export_converter(integration)
        return converter.convert_to_external()

    def to_images_export_format(self, integration):
        self.ensure_one()

        template_images_data = self._template_or_variant_to_images_export_format(
            self,
            integration,
        )

        products_images_data = []
        for product in self.product_variant_ids:
            image_data = self._template_or_variant_to_images_export_format(
                product,
                integration,
            )

            products_images_data.append(image_data)

        result = {
            'template': template_images_data,
            'products': products_images_data,
        }
        return result

    @api.model
    def _template_or_variant_to_images_export_format(self, record, integration):
        external_record = record.to_external_record(integration)

        if record._name == 'product.template':
            extra_images = record.product_template_image_ids
            default_image_field = 'image_1920'
        else:
            extra_images = record.product_variant_image_ids
            default_image_field = 'image_variant_1920'

        default_image_data = record[default_image_field]
        if default_image_data:
            default_image = {
                'data': default_image_data,
                'mimetype': _guess_mimetype(default_image_data),
                'external_image_id': record.get_mapping_any_external_id(integration, 'image'),
                'odoo_obj_name': record._name,
                'odoo_obj_id': record.id,
                'odoo_obj_field_name': default_image_field,
                'product_name': escape_trash(record.name, max_length=100),
            }
        else:
            default_image = None

        extra_images_data = []
        for image in extra_images:
            data = {
                'data': image.image_1920,
                'mimetype': _guess_mimetype(image.image_1920),
                'external_image_id': image.get_mapping_any_external_id(integration, 'image'),
                'odoo_obj_name': image._name,
                'odoo_obj_id': image.id,
                'odoo_obj_field_name': 'image_1920',
                'product_name': escape_trash(image.name, max_length=100),
            }
            extra_images_data.append(data)

        return {
            'id': external_record.code,
            'default': default_image,
            'extra': extra_images_data,
            'default_code': external_record.external_reference,
        }

    def _template_converter_update(self, template_data, integration, external_record):
        """Hook method for redefining."""
        return template_data

    def _update_template_form_architecture(self, form_data):
        active_integrations = self.get_active_integrations()

        if not active_integrations:
            return form_data

        arch_tree = etree.fromstring(form_data['arch'])

        for integration in active_integrations:
            arch_tree.append(etree.Element('filter', attrib={
                'string': integration.name.capitalize(),
                'name': f'filter_{integration.type_api}_{integration.id}',
                'domain': f'[("integration_ids", "=", {integration.id})]',
            }))

        form_data['arch'] = etree.tostring(arch_tree, encoding='unicode')

        return form_data

    def _search_pricelist_items(self, p_ids=None, i_ids=None):
        domain = [
            ('active', '=', True),
            ('product_id', '=', False),
        ]

        if i_ids:
            domain.append(('id', 'in', i_ids))
        elif p_ids:
            domain.append(('pricelist_id', 'in', p_ids))

        PricelistItem = self.env['product.pricelist.item']

        # 1. Just for `1_product` applicable option
        add_domain = [
            ('applied_on', '=', '1_product'),
            ('product_tmpl_id', '=', self.id),
        ]
        product_item_ids = PricelistItem.search(
            domain + add_domain,
        )

        # 2. Just for `2_product_category` applicable option
        categ_item_ids = PricelistItem.browse()
        if self.categ_id:
            add_domain = [
                ('applied_on', '=', '2_product_category'),
                ('categ_id', '=', self.categ_id.id),
                ('product_tmpl_id', '=', False),
            ]
            categ_item_ids = PricelistItem.search(
                domain + add_domain,
            )

        # 3. For the `3_global` applicable options
        add_domain = [
            ('applied_on', '=', '3_global'),
            ('product_tmpl_id', '=', False),
            ('categ_id', '=', False),
        ]
        global_item_ids = PricelistItem.search(
            domain + add_domain,
        )
        return product_item_ids.union(categ_item_ids, global_item_ids)

    # -------- Converter Specific Methods ---------
    def get_integration_name_field(self):
        name_field = 'name'
        if self.website_product_name:
            name_field = 'website_product_name'
        return name_field

    def get_integration_name(self, integration):
        self.ensure_one()
        return integration.convert_translated_field_to_integration_format(
            self, self.get_integration_name_field()
        )

    def get_default_category(self, integration):
        self.ensure_one()
        default_category = self.default_public_categ_id
        if default_category:
            return default_category.to_external_or_export(integration)
        else:
            return None

    def get_categories(self, integration):
        return [
            x.to_external_or_export(integration)
            for x in self.public_categ_ids
        ]

    def get_taxes(self, integration):
        result = []
        integration_company_taxes = self.taxes_id.filtered(
            lambda x: x.company_id == integration.company_id
        )
        for tax in integration_company_taxes:
            external_tax = tax.to_external_record(integration)

            external_tax_group = self.env['integration.account.tax.group.external'].search([
                ('integration_id', '=', integration.id),
                ('external_tax_ids', '=', external_tax.id),
            ], limit=1)

            if not external_tax_group:
                raise ValidationError(_(
                    'It is not possible export product to e-Commerce System, because you '
                    'haven\'t defined Tax Group for External Tax "%s". Please,  click '
                    '"Quick Configuration" button on your integration "%s" to define that mapping.'
                ) % (external_tax.code, integration.name))

            result.append({
                'tax_id': external_tax.code,
                'tax_group_id': external_tax_group.code,
            })

        return result

    def get_product_features(self, integration):
        return [
            {
                'id': feature_line.feature_id.to_external_or_export(integration),
                'id_feature_value': feature_line.feature_value_id.to_external_or_export(integration)
            }
            for feature_line in self.feature_line_ids
        ]

    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        ctx = dict(skip_product_export=True)
        template = super(ProductTemplate, self.with_context(**ctx)).copy(default=default)

        vals = self._get_empty_mandatory_fields_vals()
        if vals:
            template.product_variant_ids.write(vals)

        template.feature_line_ids = [
            (0, 0, {
                'feature_id': feature_line.feature_id.id,
                'feature_value_id': feature_line.feature_value_id.id,
            })
            for feature_line in self.feature_line_ids
        ]
        return template

    def _get_empty_mandatory_fields_vals(self):
        integrations = self._get_enabled_integrations()
        mandatory_fields = integrations.sudo().mapped('mandatory_fields_initial_product_export')
        required_fields = [
            x for x, y in self.env['product.product']._fields.items() if y.required
        ]
        return {x.name: False for x in mandatory_fields if x.name not in required_fields}

    def action_run_refresh_product_info_from_external(self):
        allowed_integrations = self.product_variant_ids.mapped('integration_ids')

        if not allowed_integrations:
            raise UserError(_(
                'This product is not yet connected with any sales channel '
                '(Shopify/Prestashop/Magento 2/Woocommerce). Please, first do initial '
                'product import and mapping per corresponding connector Documentation and '
                'then you will be able to refresh product information from an external system.'
            ))

        return {
            'name': _('Refresh Product Info From External'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'refresh.products.wizard',
            'target': 'new',
            'context': {
                'template_ids': self.ids,
                'allowed_integration_ids': allowed_integrations.ids,
            },
        }

    def _create_variant_ids(self):
        if not self.env.context.get('integration_product_creating'):
            return super(ProductTemplate, self)._create_variant_ids()

        for tmpl in self:
            attr_lines = tmpl.attribute_line_ids
            if not attr_lines or len(attr_lines) == len(attr_lines.value_ids):
                super(ProductTemplate, tmpl)._create_variant_ids()

        return True

    def _is_combination_possible_by_config(self, combination, ignore_no_variant=False):
        self.ensure_one()

        if self.env.context.get('integration_product_creating'):
            variant = self._get_variant_for_combination(combination)
            ProductMapping = self.env['integration.product.product.mapping']

            if variant and len(variant) == 1:
                if ProductMapping.search_count([('product_id', '=', variant.id)]) != 0:
                    return True

        return super(ProductTemplate, self)._is_combination_possible_by_config(
            combination, ignore_no_variant)

    def generate_variants(self):
        self.ensure_one()

        Product = self.env['product.product']
        AttributeValue = self.env['product.template.attribute.value']
        variants_to_create = list()
        ctx = dict(skip_product_export=True)

        lines_without_no_variants = self.attribute_line_ids._without_no_variant_attributes()
        all_variants = self.with_context(active_test=False).product_variant_ids

        variants_to_unlink = all_variants.with_context(**ctx).filtered(
            lambda x: not x.product_template_attribute_value_ids)
        current_variants = all_variants - variants_to_unlink
        integration_ids = variants_to_unlink.mapped('integration_ids')

        if variants_to_unlink:
            for variant in variants_to_unlink:
                for integration in integration_ids:
                    ext_records = variant.to_external_record(integration, raise_error=False)
                    if ext_records:
                        ext_records.unlink()

            variants_to_unlink.write({'integration_ids': [(6, 0, [])]})
            variants_to_unlink._unlink_or_archive()

        existing_combinations = {
            variant.product_template_attribute_value_ids: variant for variant in current_variants
        }
        all_combinations = itertools.product(*[
            line.product_template_value_ids._only_active() for line in lines_without_no_variants
        ])

        for combination_tuple in all_combinations:
            combination = AttributeValue.concat(*combination_tuple)
            if combination not in existing_combinations:
                variant_vals = self._prepare_variant_values(combination)
                if integration_ids:
                    variant_vals['integration_ids'] = integration_ids
                variants_to_create.append(variant_vals)

        if variants_to_create:
            return Product.create(variants_to_create)
        return Product

    def _prepare_integration_ids(self):
        if len(self.product_variant_ids) > 1:
            return self._prepare_default_integration_ids()
        return [(6, 0, self.integration_ids.ids)]

    def show_product_mappings(self):
        """
            Open a list view with mappings for the current product.
        """
        self.ensure_one()

        view_id = self.env.ref('integration.integration_product_template_mapping_view_tree')
        TemplateMapping = self.env['integration.product.template.mapping']
        mapping_ids = TemplateMapping.search([('template_id', '=', self.id)])

        return {
            'type': 'ir.actions.act_window',
            'name': 'Products Mappings',
            'res_model': 'integration.product.template.mapping',
            'context': {'product_template_mapping': 1},
            'view_mode': 'tree',
            'view_id': view_id.id,
            'domain': [('id', 'in', mapping_ids.ids)],
            'target': 'current',
        }
