# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, _
from odoo.exceptions import UserError


PRODUCT_BUSINESS_MODELS = [
    'product.product',
    'product.template',
]


class ProductEcommerceField(models.Model):
    _name = 'product.ecommerce.field'
    _description = 'Ecommerce field depending on integration type'

    name = fields.Char(
        string='Description',
        required=True,
        help='Here we have Field name like it is displayed on user interface'
    )

    technical_name = fields.Char(
        string='Field Name in API',
        required=True,
        help='Here we have Field like it is referred to in the API',
    )

    type_api = fields.Selection(
        selection=[
            ('no_api', 'Not Use API'),
        ],
        string='Api service',
        required=True,
        ondelete={
            'no_api': 'cascade',
        },
        help='Every field exists only together with it\'s e-commerce system. '
             'So here we define which e-commerce system this field is related to. '
             'This should be updated for every new integration.',
    )

    send_method = fields.Char(
        string='Export Method Name',
        help='In some cases calculation of the field values can be rather complex. '
             'So here you can write name of the python method that will be used to retrieve '
             'the value from object of selected Model. Note that method should accept at '
             'list one argument (current integration).',
    )

    value_converter = fields.Selection(
        selection=[
            ('simple', 'Simple Field'),
            ('translatable_field', 'Translatable Field'),
            ('python_method', 'Method in Model'),
        ],
        string='Value Converter',
        required=True,
        help='Define here pre-defined field converters. That will be used to retrieve values from '
             'Odoo and push them to the external e-Commerce system.',
        default='simple',
    )

    default_for_update = fields.Boolean(
        string='Default for Update',
        help='By default fields that are available in the fields mapping will be ALL used to '
             'create new product record on external e-commerce system. But after record is '
             'created, we do not want to mess up and override changes that are done for '
             'that field on external system. Hence we can specify here if that field will '
             'be default also for Updating. Value from here will be copied to the mapping '
             'on Sales Integration creation.',
    )

    default_for_import = fields.Boolean(
        string='Default for Import to Odoo',
        default=False,
        help='By default fields that are available in the fields mapping will be ALL used to '
             'create new product Odoo. But after record is '
             'created, we do not want to mess up and override changes that are done for '
             'that field in Odoo. Hence we can specify here if that field will '
             'be default also for Import in Odoo. Value from here will be copied to the mapping '
             'on Sales Integration creation.',
    )

    is_default = fields.Boolean(
        string='Is Default for this API',
        default=True,
        help='When new Integration of API type is created, field mapping will '
             'be automatically pre-created based on this checkbox. So user do not '
             'need to create mapping manually',
    )

    odoo_model_id = fields.Many2one(
        string='Odoo Model',
        comodel_name='ir.model',
        required=True,
        ondelete='cascade',
        domain=[('model', 'in', PRODUCT_BUSINESS_MODELS)],
        help='Here we select model which will be used to retrieve data from'
    )

    odoo_model_name = fields.Char(
        related='odoo_model_id.model',
        store=True,
    )

    odoo_field_id = fields.Many2one(
        string='Odoo Field',
        comodel_name='ir.model.fields',
        ondelete='cascade',
        domain='[("model_id", "=", odoo_model_id)]',
        help='For simple fields you can select here field name from defined '
             'model to retrieve information from',
    )

    odoo_field_name = fields.Char(
        string='Odoo Field Name',
        related='odoo_field_id.name',
        store=True,
    )

    receive_method = fields.Char(
        string='Import Method Name',
        help='In some cases calculation of the field values can be rather complex. '
             'So here you can write name of the python method that will be used to retrieve '
             'the value from object of selected Model. Note that method should accept at '
             'list one argument (current integration).',
    )

    trackable_fields_ids = fields.Many2many(
        string='Trackable Fields',
        comodel_name='ir.model.fields',
        ondelete='cascade',
        domain='[("model_id", "=", odoo_model_id)]',
        help='Here we can select fields that will run export process when they are updated.',
    )

    is_private = fields.Boolean(
        string='Private',
        help='Technical property for developers needs',
    )

    mapping_ids = fields.One2many(
        comodel_name='product.ecommerce.field.mapping',
        inverse_name='ecommerce_field_id',
        string='Mappings',
    )

    @property
    def on_template(self):
        self.ensure_one()
        return self.odoo_model_name == 'product.template'

    @property
    def on_variant(self):
        self.ensure_one()
        return self.odoo_model_name == 'product.product'

    @property
    def converter_action_name(self):
        return f'_get_{self.value_converter}_value'

    @property
    def is_translatable(self):
        return self.value_converter == 'translatable_field'

    @property
    def is_simple(self):
        return self.value_converter == 'simple'

    @property
    def is_converted(self):
        return self.value_converter == 'python_method'

    def get_mapping_for_integration(self, integration_id):
        assert len(self) <= 1, _('Recordsets not allowed')

        mapping = self.mapping_ids.filtered(lambda x: x.integration_id.id == integration_id)

        if len(mapping) > 1:
            raise UserError(
                _('%s: Multiple mappings found for the ecommerce field %s --> %s')
                % (self.env['sale.integration'].browse(integration_id).name, self.name, mapping)
            )

        if not mapping:
            mapping = self.with_context(active_test=False).mapping_ids\
                .filtered(lambda x: x.integration_id.id == integration_id)[:1]
            mapping.mark_active()

        return mapping

    def mark_mapping_inactive(self, integration_id):
        assert len(self) <= 1, _('Recordsets not allowed')
        mapping = self.mapping_ids.filtered(lambda x: x.integration_id.id == integration_id)

        return mapping.mark_inactive()

    def _ensure_mapping(self, integration_id):
        self.ensure_one()

        if self.is_private:
            return True

        mapping = self.get_mapping_for_integration(integration_id)

        if not mapping:
            self._create_mapping(integration_id)

        return True

    def _create_mapping(self, integration_id):
        return self.env['product.ecommerce.field.mapping'].create({
            'ecommerce_field_id': self.id,
            'integration_id': integration_id,
            'send_on_update': self.default_for_update,
            'receive_on_import': self.default_for_import,
        })
