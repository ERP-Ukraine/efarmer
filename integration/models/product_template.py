# See LICENSE file for full copyright and licensing details.

import itertools
import logging
from typing import List
from functools import reduce

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

from odoo.addons.integration_queue_job.job import Job

from ..tools import ExternalImage
from ..exceptions import NotMappedToExternal
from ..models.sale_integration import EXPORT_EXTERNAL_BLOCK


_logger = logging.getLogger(__name__)

INTEGRATION_PRODUCT_TEMPLATE_ACTIONS = [
    'Export to Stores', 'Export Stock to Stores',
    'Manage Store Connections', 'Refresh from Store',
    'View Synchronization History',
]


class ProductTemplate(models.Model):
    _name = 'product.template'
    _inherit = [  # Order of items is important
        'product.template',
        'integration.product.mixin',
        'integration.model.mixin',
        'integration.image.mixin',
    ]
    _description = 'Product Template'

    _image_name = 'image_1920'
    _image_names = 'integration_template_image_ids'
    _internal_reference_field = 'default_code'

    integration_default_category_id = fields.Many2one(
        comodel_name='ecommerce.product.category',
        string='Default Category',
    )

    integration_category_ids = fields.Many2many(
        comodel_name='ecommerce.product.category',
        relation='ecommerce_product_category_product_template_rel',
        string='Website Product Category',
    )

    available_category_ids = fields.Many2many(
        comodel_name='ecommerce.product.category',
        compute='_compute_available_category_ids',
        string='Website Product Category Filter',
    )

    integration_template_image_ids = fields.One2many(
        comodel_name='ecommerce.product.image',
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
             'E-Commerce System instead of standard field.'
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

    integration_mapping_ids = fields.One2many(
        comodel_name='integration.product.template.mapping',
        inverse_name='template_id',
        string='E-Commerce Store Mappings',
    )

    mapping_count = fields.Integer(
        string='Mapping Count',
        compute='_compute_mapping_count',
        help='The number of mappings associated with this product.',
    )

    external_tag_group_ids = fields.One2many(
        comodel_name='product.template.external.tag.group',
        inverse_name='product_tmpl_id',
        string='External Tags',
    )

    integration_company_mismatch = fields.Boolean(
        compute='_compute_integration_company_mismatch',
        help='Technical field used to detect multi-company mismatch.'
             'It is True when this product belongs to a company, but at least one of the selected '
             'e-commerce integrations belongs to a different company.'
             'Make sure the product company matches the integration company, or remove mismatching integrations.'
    )

    def _get_view_postprocessed(self, view, arch, **options):
        # Redefined the standard method to update a form-view architecture
        arch, models_ = super()._get_view_postprocessed(view, arch, **options)

        if view.type == 'form':
            arch = self._exclude_convert_to_webp_option(
                arch,
                '//field[@name="image_1920"] | //field[@name="product_template_image_ids"]',
            )

        return arch, models_

    @property
    def integration_should_export_inventory(self):
        """Determine if the product template should be included in inventory export."""
        return (
            (self.is_consumable_storable or (self.type == 'consu' and bool(self.bom_ids)))
            and not self.exclude_from_synchronization
            and not self.exclude_from_synchronization_stock
        )

    @api.depends('company_id', 'integration_ids', 'integration_ids.company_id')
    def _compute_integration_company_mismatch(self):
        """
        Compute whether this template company conflicts with any linked integration company.

        If `company_id` is not set, mismatch is always False.
        """
        for rec in self:
            if not rec.company_id:
                rec.integration_company_mismatch = False
                continue
            mismatched = rec.integration_ids.filtered(
                lambda i: i.company_id and i.company_id != rec.company_id
            )
            rec.integration_company_mismatch = bool(mismatched)

    def _compute_mapping_count(self):
        for rec in self:
            rec.mapping_count = len(rec.integration_mapping_ids)

    @api.depends('attribute_line_ids')
    def _compute_used_dynamic_attributes(self):
        for template in self:
            all_lines = template.valid_product_template_attribute_line_ids
            lines_without_no_variant = all_lines._without_no_variant_attributes()
            lines = lines_without_no_variant.filtered(lambda line: len(line.value_ids) != 1)

            combinations_count = 0
            value_count = [len(x.value_ids) for x in lines]
            if value_count:
                combinations_count = reduce(lambda a, b: a * b, value_count)
            variants_count = len(template.with_context(active_test=False).product_variant_ids)
            need_create_variants = combinations_count > variants_count
            template.is_used_dynamic_attributes = template.has_dynamic_attributes() and \
                need_create_variants

    def get_or_create_tag_group(self, integration_id: int, language_id: int = False):
        self.ensure_one()

        group = self.env['product.template.external.tag.group'].search([
            ('product_tmpl_id', '=', self.id),
            ('integration_id', '=', integration_id),
            ('external_language_id', '=', language_id),
        ], limit=1)

        if not group:
            group = self.env['product.template.external.tag.group'].create({
                'product_tmpl_id': self.id,
                'integration_id': integration_id,
                'external_language_id': language_id,
            })

        return group

    def get_integration_kits(self, integration_id: int, limit=1):
        self.ensure_one()

        integration = self.env['sale.integration'].browse(integration_id)

        kit = self.env['mrp.bom'].search([
            ('active', '=', True),
            ('type', '=', 'phantom'),
            ('product_tmpl_id', '=', self.id),
            ('company_id', 'in', (integration.company_id.id, False)),
        ], order='sequence, product_id, id', limit=limit)

        return kit

    def _get_tmpl_id_for_log(self):
        return self.id

    def _export_inventory_on_template(self, integration_id: int):
        self.ensure_one()

        integration = self.env['sale.integration'].browse(integration_id)
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
            context = {
                'company_id': integration.company_id.id,
                'job_integration_id': integration.id,
                'job_integration_job_type': 'inventory',
                'job_template_id': self.id,
            }
            job = integration.with_context(**context).with_delay(**job_kwargs) \
                .export_inventory_for_variant_with_delay(variant)
            result.append(job)

        return result

    def open_related_jobs(self):
        self.ensure_one()
        externals = self.integration_mapping_ids.mapped('external_template_id')

        jobs = self.env['queue.job'].search([
            '|',
            ('external_template_id', 'in', externals.ids),
            ('template_id', '=', self.id),
        ])

        view_ids = [
            (0, 0, {'view_mode': 'list', 'view_id': self.env.ref('integration.view_integration_queue_job_list').id}),
            (0, 0, {'view_mode': 'form', 'view_id': self.env.ref('integration.view_integration_queue_job_form').id}),
        ]

        return {
            'type': 'ir.actions.act_window',
            'name': _('Jobs History'),
            'res_model': 'queue.job',
            'view_mode': 'list,form',
            'view_ids': view_ids,
            'domain': [('id', 'in', jobs.ids)],
            'target': 'current',
        }

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
        search=_search_integrations,
        domain=[('state', '=', 'active')],
        string='E-Commerce Stores',
        default=lambda self: self._prepare_default_integration_ids(),
        tracking=True,
        help='Allow to select which stores this product should be synchronized to. '
             'By default it syncs to all.',
    )

    @api.depends('product_variant_ids', 'product_variant_ids.integration_ids')
    def _compute_integration_ids(self):
        # We can't use plain call of self._compute_template_field_from_variant_field('integration_ids') because it
        # works incorrectly with inactive products (when self is mutple records and some of them are inactive).
        for template in self:
            if not template.active:
                template = template.with_context(active_test=False)

            template._compute_template_field_from_variant_field('integration_ids')

    def _inverse_integration_ids(self):
        self._set_product_variant_field('integration_ids')

    @api.depends('integration_category_ids')
    def _compute_available_category_ids(self):
        for rec in self:
            category_ids = list()
            rec_categories = rec.integration_category_ids

            if not rec_categories:
                category_ids = rec_categories.search([]).ids
            else:
                for category in rec_categories:
                    category_ids.extend(
                        category.parse_parent_recursively()
                    )

            rec.available_category_ids = [(6, 0, category_ids)]

    @api.model_create_multi
    def create(self, vals_list):
        # We need to avoid calling export separately from template and variant.
        ctx = dict(self.env.context, from_product_template=True, from_product_create=True)
        from_product_product = ctx.pop('from_product_product', False)

        templates = super(ProductTemplate, self.with_context(ctx)).create(vals_list)

        for template, vals in zip(templates, vals_list):
            if 'integration_ids' in vals:
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
        result = self.env['queue.job']

        for integration in self._get_enabled_integrations():
            export_template = first_export or integration._is_need_export_product(vals)
            export_images = integration._is_need_export_images(vals)
            integration = integration.with_context(company_id=integration.company_id.id)

            job = None
            # A. Export template + images
            if export_template:
                kw = integration._job_kwargs_export_template(self, export_images)
                context = {
                    'company_id': integration.company_id.id,
                    'job_integration_id': integration.id,
                    'job_integration_job_type': 'product',
                    'job_template_id': self.id,
                }
                job = integration.with_context(**context).with_delay(**kw) \
                    .export_template(self, export_images=export_images, make_validation=True)

            # B. Export only images
            elif export_images:
                kw = integration._job_kwargs_export_images(self)
                context = {
                    'company_id': integration.company_id.id,
                    'job_integration_id': integration.id,
                    'job_integration_job_type': 'product',
                    'job_template_id': self.id,
                }
                job = integration.with_context(**context).with_delay(**kw) \
                    .export_template_images_verbose(self.id)

            if job:
                result |= job.db_record() if isinstance(job, Job) else job

        _logger.info('%s: Integration export jobs: %s', self, result)

        return result

    def _get_enabled_integrations(self):
        self.ensure_one()

        integrations = self.mapped('product_variant_ids.integration_ids').filtered(
            lambda i: i.is_product_template_export_enabled
        )

        if self.company_id:
            integrations = integrations.filtered(lambda x: x.company_id == self.company_id)

        return integrations

    @api.onchange('integration_category_ids')
    def _onchange_integration_category_ids(self):
        category_ids = list()

        for category in self.integration_category_ids:
            category_ids.extend(
                category._origin.parse_parent_recursively()
            )

        category_id = self.integration_default_category_id.id
        if category_id and category_ids and category_id not in category_ids:
            self.integration_default_category_id = False

    def change_external_integration_template(self):
        message_pattern = self._get_change_external_message()
        active_ids = self.env.context.get('active_ids')
        if not active_ids:
            return

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
            'name': _('Manage Store Connections'),
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
            'be synchronised to specific stores. Stores only in "Active"'
            'state are displayed below. Note that you can define this also on'
            '"E-Commerce Integration" tab of every product/product variant individually.'
        )

    def export_images_to_integration(self):
        self.ensure_one()
        integrations = self.mapped('product_variant_ids.integration_ids').filtered(
            lambda x: x.is_active and x.allow_export_images
        )

        for integration in integrations:
            kw = integration._job_kwargs_export_images(self)

            context = {
                'company_id': integration.company_id.id,
                'job_integration_id': integration.id,
                'job_integration_job_type': 'product',
                'job_template_id': self.id,
            }
            integration \
                .with_context(**context) \
                .with_delay(**kw).export_template_images_verbose(
                    self.id,
                    erase_mappings=self.env.context.get('integration_erase_mappings'),
                )

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
                context = {
                    'company_id': self.company_id.id,
                    'job_integration_job_type': 'product',
                    'job_related_record_model': self._name,
                    'job_related_record_ids': templates_block.ids,
                }
                templates_block = templates_block.with_context(**context).with_delay(
                    priority=11,
                    description=f'Export Templates. Prepare Templates ({block})',
                )

            templates_block.trigger_export_by_block(
                export_images, integrations, manual_trigger,
            )

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
            template_integrations = integrations
            if template.company_id:
                template_integrations = integrations.filtered(lambda x: x.company_id == template.company_id)

            variant_integrations = template.product_variant_ids.mapped('integration_ids')
            enabled_integrations = template_integrations.filtered(lambda x: x in variant_integrations)

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
                context = {
                    'company_id': integration.company_id.id,
                    'job_integration_id': integration.id,
                    'job_integration_job_type': 'product',
                    'job_template_id': template.id,
                }
                integration \
                    .with_context(**context) \
                    .with_delay(**job_kwargs).export_template(template, **kwargs)

    def _check_filling_mandatory_fields(self, integration):
        variant_ids = self.product_variant_ids
        mandatory_fields = integration.sudo().mandatory_fields_initial_product_export

        for field_name in mandatory_fields.mapped('name'):
            if not all(variant[field_name] for variant in variant_ids):
                message = _(
                    'The product template "%s" or one of its variants does not have '
                    'the mandatory field "%s" filled.\n\n'
                    'Please ensure that the field "%s" is populated for all variants before proceeding with the export.'
                ) % (self.display_name, field_name, field_name)
                return False, message

        return True, ''

    def validate_in_odoo(self, integration, raise_error=False):
        self.ensure_one()

        def not_valid(message):
            if raise_error:
                raise UserError(message)
            return False, message

        # 1. Check mandatory fields
        external_id = self.get_external_code(integration.id)
        if not external_id:
            is_valid, message = self._check_filling_mandatory_fields(integration)
            if not is_valid:
                return not_valid(message)

        # 2. Check Internal-references
        variants = self.product_variant_ids.filtered(
            lambda x: integration.id in x.integration_ids.ids
        )
        if not variants:
            message = _(
                'The product template "%s" has no variants with the integration "%s" set.', self.name, integration.name,
            )
            return not_valid(message)

        ref_field = integration.product_reference_name
        internal_references = variants.mapped(ref_field)

        if not all(internal_references):
            message = _(
                'The product template "%s" or one of its variants does not have an internal reference defined.\n\n'
                'This field is mandatory for the integration as it is used for automatic mapping. '
                'Please ensure that all product variants have the internal reference field populated.'
            ) % self.name
            return not_valid(message)

        if len(set(internal_references)) < len(internal_references):
            message = _(
                'Duplicate internal reference(s) detected: %s.\n\n'
                'Each variant must have a unique internal reference for the product template to work correctly. '
                'Please resolve these duplicate references before continuing.'
            ) % ', '.join(x for x in internal_references if internal_references.count(x) > 1)
            return not_valid(message)

        # 2.1 We also should check if product do not have duplicated internal reference
        # As in Odoo standard duplicated reference is allowed
        # But we do not want to have it in external E-Commerce System
        records = self.env['product.product'].search([
            (ref_field, 'in', internal_references),
            ('product_tmpl_id.exclude_from_synchronization', '=', False),
            ('company_id', 'in', [False, integration.company_id.id]),
        ])

        if len(records) > len(internal_references):
            message = _(
                'Duplicate internal reference(s) detected: %s.\n\n'
                'Each product must have a unique internal reference for this integration to work correctly. '
                'Please resolve these duplicate references before continuing.'
            ) % ', '.join((records - variants).mapped(ref_field))
            return not_valid(message)

        return True, ''

    def to_export_format(self, integration: 'models.Model'):
        if not self.active:
            self = self.with_context(active_test=False)

        variants = self.prepare_integration_variants(integration.id)

        products = []
        for variant in variants:
            data = variant.to_export_format(integration)
            products.append(data)

        external_record = self.to_external_record(integration, raise_error=False)

        result = {
            'id': self.id,
            'odoo_external_id': external_record.id,
            'external_id': external_record.code,
            'type': self.type,
            'kits': self._get_kits(integration.id),
            'products': products,
            'variants_count': len(variants),
            'has_attributes': bool(self.attribute_line_ids.filtered(lambda x: not x.exclude_from_synchronization)),
            'fields': self.calculate_export_fields_data(integration.id),
        }

        return result

    def to_images_export_format(self, integration) -> List[ExternalImage]:
        self.ensure_one()

        external_template = self.to_external_record(integration)

        if not external_template.image_mappings_lack_or_in_none_state:
            external_template.all_image_external_ids.unlink()

        external_template._mark_image_mappings_as_pending()

        result = external_template._prepare_images_mappings_to_export()

        # Skip images from single variant. They are all on the parent template (use the child_ids property)
        for external_variant in external_template.child_ids:
            images = external_variant._prepare_images_mappings_to_export()
            result.extend(images)

        external_template._unlink_image_mappings_pending()

        return result

    def import_template_hook(self, integration_id: int, force_import: bool = False):
        """Hook for import template"""
        pass

    def export_template_hook(self, integration_id: int, force_export: bool = False):
        """Hook for export template"""
        pass

    def _get_extra_images(self):
        images = super()._get_extra_images()
        return images.filtered(lambda x: not x.product_variant_id)

    def _search_pricelist_items(self, p_ids=None, i_ids=None):
        domain = [
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

    def convert_pricelists(self, integration_id: int, pricelist_ids=None, item_ids=None, raise_error=False):
        force_sync_pricelist = self.to_force_sync_pricelist
        if force_sync_pricelist:
            pricelist_ids = item_ids = None

        def _format_result(prices):
            return (
                self.id,
                self._name,
                self.get_external_code(integration_id),
                prices,
                force_sync_pricelist,
            )

        t_prices_list = self._collect_specific_prices(
            integration_id,
            pricelist_ids=pricelist_ids,
            item_ids=item_ids,
            raise_error=raise_error,
        )

        variant_data_list = list()
        for variant in self.prepare_integration_variants(integration_id):
            v_prices_list = variant._collect_specific_prices(
                integration_id,
                pricelist_ids=pricelist_ids,
                item_ids=item_ids,
                raise_error=raise_error,
            )
            if force_sync_pricelist or v_prices_list:
                variant_data = _format_result(v_prices_list)
                variant_data_list.append(variant_data)

        if force_sync_pricelist or t_prices_list or variant_data_list:
            tmpl_data = _format_result(t_prices_list)
            return tmpl_data, variant_data_list

        return tuple()

    # -------- Converter Specific Methods ---------

    def get_default_category(self, integration_id: int):
        self.ensure_one()

        default_category = self.integration_default_category_id

        if default_category:
            integration = self.env['sale.integration'].browse(integration_id)
            return default_category.to_external_or_export(integration)

        return None

    def get_categories(self, integration_id: int):
        integration = self.env['sale.integration'].browse(integration_id)

        return [
            x.to_external_or_export(integration)
            for x in self.integration_category_ids
        ]

    def get_taxes(self, integration_id: int):
        integration = self.env['sale.integration'].browse(integration_id)
        company = integration.company_id
        self = self.with_company(company)

        result = []
        integration_company_taxes = self.taxes_id.filtered(lambda x: x.company_id == company)

        for tax in integration_company_taxes:
            external_tax = tax.to_external_record(integration)

            external_tax_group = self.env['integration.account.tax.group.external'].search([
                ('integration_id', '=', integration.id),
                ('external_tax_ids', '=', external_tax.id),
            ], limit=1)

            if not external_tax_group:
                raise ValidationError(_(
                    'Cannot export the product to the e-commerce system because no Tax Group is defined for '
                    'the external tax "%s".\n\n'
                    'To resolve this issue, please click the "Quick Configuration" button in '
                    'the "%s" integration settings and define the Tax Group mapping.'
                ) % (external_tax.code, integration.name))

            result.append({
                'tax_id': external_tax.code,
                'tax_group_id': external_tax_group.code,
            })

        return result

    def copy(self, default=None):
        ctx = dict(skip_product_export=True)
        records = super(ProductTemplate, self.with_context(**ctx)).copy(default=default)

        for template, original_template in zip(records, self):
            vals = original_template._get_empty_mandatory_fields_vals()
            if vals:
                template.product_variant_ids.write(vals)

        return records

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
                'This product is not connected to any e-commerce store '
                '(e.g., Shopify, Prestashop, Magento 2, WooCommerce).\n\n'
                'To resolve this issue, please perform the initial product import and mapping for '
                'the relevant connector, as outlined in the corresponding connector\'s documentation.\n'
                'Once the product is properly mapped, you will be able to refresh product information from '
                'the external system.'
            ))

        return {
            'name': _('Refresh from Store'),
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
        if not self.env.context.get('integration_first_time_import'):
            return super(ProductTemplate, self)._create_variant_ids()

        for tmpl in self:
            attr_lines = tmpl.attribute_line_ids
            if not attr_lines or len(attr_lines) == len(attr_lines.value_ids):
                super(ProductTemplate, tmpl)._create_variant_ids()

        return True

    def _is_combination_possible_by_config(self, combination, ignore_no_variant=False):
        self.ensure_one()

        if self.env.context.get('integration_first_time_import'):
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
        """TODO: drop it after 1.17.0 release"""
        return {}

    def prepare_integration_variants(self, integration_id: int):
        """
            Returns a sorted recordset of product variants filtered by integration.

            The method filters the product variant records based on their integration_ids and
                sorts them based on their
            attribute values. The sorting is done in the following order:
                1. The attribute ID of the attribute value
                2. The sequence number of the attribute value.

            Returns:
                recordset: A sorted recordset of product variants filtered by integration.
        """
        variants = self.product_variant_ids.filtered(
            lambda x: integration_id in x.integration_ids.ids).sorted(
            key=lambda v: [
                (attr.attribute_id.id, attr.sequence)
                for attr in
                v.product_template_attribute_value_ids.mapped('product_attribute_value_id')
            ])

        return variants

    def _get_template_attribute_values(self, integration_id: int, attribute_value_ids: list):
        ProductAttributeValue = self.env['product.attribute.value']
        ProductTemplateAttributeValue = self.env['product.template.attribute.value']
        integration = self.env['sale.integration'].browse(integration_id)

        odoo_attribute_value_ids = []
        for ext_attribute_value_id in attribute_value_ids:
            if ext_attribute_value_id == '0':
                continue

            attribute_value_id = ProductAttributeValue.from_external(
                integration,
                ext_attribute_value_id,
            )
            odoo_attribute_value_ids.append(attribute_value_id.id)

        if not odoo_attribute_value_ids:
            return ProductTemplateAttributeValue.browse()

        return ProductTemplateAttributeValue.search([
            ('product_attribute_value_id', 'in', odoo_attribute_value_ids),
            ('product_tmpl_id', '=', self.id),
        ])

    def _get_kits(self, integration_id: int):
        integration = self.env['sale.integration'].browse(integration_id)

        # Kit/bundle export is only supported for PrestaShop and Magento 2 connectors
        if not (integration.is_integration_prestashop or integration.is_integration_magento_two):
            return []

        # If the integration is configured to ignore BOMs, return an empty list
        if integration.ignore_boms_for_product_export:
            return []

        result = []
        kit = self.get_integration_kits(integration_id)

        for line in kit.bom_line_ids:
            try:
                external_record = line.product_id.to_external_record(integration)
            except NotMappedToExternal as ex:
                raise UserError(
                    _(
                        'The product "%s" cannot be exported because one or more of its components have '
                        'not been exported yet.\n'
                        'Please review the following:\n'
                        '1. Ensure that the component products have been exported by triggering '
                        'their export if necessary.\n'
                        '2. If the component products are still pending in the export queue, please wait for '
                        'the export process to complete.\n'
                        '3. If there are failed export jobs for the component products, review '
                        'the errors, fix them, and restart the failed jobs.\n\n'
                        'Details: %s'
                    ) % (line.product_id.display_name, ex.args[0])
                )

            result.append({
                'qty': line.product_qty,
                'name': line.display_name,
                'product_id': external_record.code,
                'external_reference': external_record.external_reference,
            })

        return result

    @api.model
    def get_views(self, views, options=None):
        """
        Override to group actions related to e-commerce integrations
        to the separate group in the toolbar.
        """
        res = super().get_views(views, options)

        for action in res.get('views', {}).get('form', {}).get('toolbar', {}).get('action', []):
            if action.get('name', '') in INTEGRATION_PRODUCT_TEMPLATE_ACTIONS:
                action['groupNumber'] = 999

        for action in res.get('views', {}).get('list', {}).get('toolbar', {}).get('action', []):
            if action.get('name', '') in INTEGRATION_PRODUCT_TEMPLATE_ACTIONS:
                action['groupNumber'] = 999

        return res
