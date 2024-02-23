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

    ecommerce_field_id = fields.Many2one(
        comodel_name='product.ecommerce.field',
        required=True,
        domain='[("type_api","=",integration_api_type)]',
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

    odoo_field_id = fields.Many2one(
        comodel_name='ir.model.fields',
        related='ecommerce_field_id.odoo_field_id',
        readonly=True,
        store=True,
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

    @api.onchange('ecommerce_field_id')
    def _onchange_ecommerce_field_id(self):
        self.send_on_update = self.ecommerce_field_id.default_for_update
        self.receive_on_import = self.ecommerce_field_id.default_for_import

    def add_mapping_using_another_field(self, type_api, field_list):
        integrations = self.env['sale.integration'].with_context(active_test=False).search([
            ('type_api', '=', type_api)
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

    @api.model_create_multi
    def create(self, vals):
        res = super(ProductEcommerceFieldMapping, self).create(vals)
        for rec in res:
            if rec.ecommerce_field_id:
                rec.write({
                    'send_on_update': rec.ecommerce_field_id.default_for_update,
                    'receive_on_import': rec.ecommerce_field_id.default_for_import,
                })
        return res

    def get_translatable_template_api_names(self):
        mappings = self._search_translatable_fields()
        model_id = self.env.ref('product.model_product_template').id
        mappings = mappings.filtered(
            lambda x: x.ecommerce_field_id.odoo_model_id.id == model_id
        )
        return mappings.mapped('technical_name')

    def get_translatable_variant_api_names(self):
        mappings = self._search_translatable_fields()
        model_id = self.env.ref('product.model_product_product').id
        mappings = mappings.filtered(
            lambda x: x.ecommerce_field_id.odoo_model_id.id == model_id
        )
        return mappings.mapped('technical_name')

    def _search_translatable_fields(self):
        domain, translatable_field = list(), 'translatable_field'
        integration_id = self.env.context.get('integration_id')
        if integration_id:
            domain.append(('integration_id', '=', integration_id))

        mapping_ids = self.search(domain)

        return mapping_ids.filtered(
            lambda x: x.ecommerce_field_id.value_converter == translatable_field
        )
