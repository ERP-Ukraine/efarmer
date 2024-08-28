# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api


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

    ecommerce_field_id = fields.Many2one(
        comodel_name='product.ecommerce.field',
        required=True,
        domain='[("type_api", "=", integration_api_type)]',
        ondelete='cascade',
    )

    integration_api_type = fields.Selection(
        related='integration_id.type_api',
        readonly=True,
        store=True,
    )

    integration_id = fields.Many2one(
        comodel_name='sale.integration',
        required=True,
        ondelete='cascade',
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
        related='ecommerce_field_id.odoo_field_name',
    )

    send_on_update = fields.Boolean(
        string='Send field for updating',
        default=False,
        help='By default fields that are available in the fields mapping will be ALL used '
             'to create new product record on external e-commerce system. But after record '
             'is created, we do not want to mess up and override changes that are done for '
             'that field on external system. Hence we can specify here if that field will be '
             'sent when updating product. ',
    )

    receive_on_import = fields.Boolean(
        string='Receive field on import',
        default=False,
        help='By default fields that are available in the fields mapping will be ALL used '
             'to create new product in Odoo. But after record is created, '
             'we do not want to mess up and override changes that are done for '
             'that field in Odoo. Hence we can specify here if that field will be '
             'received when importing product. ',
    )

    trackable_fields_rel = fields.Many2many(
        string='Trackable Fields',
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
        self.send_on_update = self.ecommerce_field_id.default_for_update
        self.receive_on_import = self.ecommerce_field_id.default_for_import

    def mark_active(self):
        return self.write({'active': True})

    def mark_inactive(self):
        return self.write({'active': False})

    @api.model_create_multi
    def create(self, vals_list):
        res = super(ProductEcommerceFieldMapping, self).create(vals_list)

        for vals, rec in zip(vals_list, res):
            update_vals = dict()

            if 'send_on_update' not in vals:
                update_vals['send_on_update'] = rec.ecommerce_field_id.default_for_update
            if 'receive_on_import' not in vals:
                update_vals['receive_on_import'] = rec.ecommerce_field_id.default_for_update

            if update_vals:
                rec.write(update_vals)

        return res

    def get_translatable_template_api_names(self):
        mappings = self._search_translatable_fields()
        mappings = mappings.filtered(lambda x: x.ecommerce_field_id.on_template)
        return mappings.mapped(lambda x: x.technical_name)

    def get_translatable_variant_api_names(self):
        mappings = self._search_translatable_fields()
        mappings = mappings.filtered(lambda x: x.ecommerce_field_id.on_variant)
        return mappings.mapped(lambda x: x.technical_name)

    def _search_translatable_fields(self):
        domain = list()

        integration_id = self.env.context.get('integration_id')
        if integration_id:
            domain.append(('integration_id', '=', integration_id))

        return self.search(domain).filtered(lambda x: x.ecommerce_field_id.is_translatable)

    def add_mapping_using_another_field(self, type_api, field_list):  # Used in old migrations
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
                        'send_on_update': mapping_old.send_on_update,
                        'receive_on_import': mapping_old.receive_on_import,
                    })
