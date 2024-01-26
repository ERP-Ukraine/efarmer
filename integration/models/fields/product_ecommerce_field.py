# See LICENSE file for full copyright and licensing details.

from odoo import models, fields


PRODUCT_BUSINESS_MODELS = [
    'product.product',
    'product.template',
]


class ProductEcommerceField(models.Model):
    _name = 'product.ecommerce.field'
    _description = 'Ecommerce field depending on integration type'

    name = fields.Char(
        string='Field Name',
        required=True,
        help='Here we have Field name like it is displayed on user interface'
    )

    technical_name = fields.Char(
        string='Field Name in API',
        required=True,
        help='Here we have Field like it is referred to in the API',
    )

    type_api = fields.Selection(
        [('no_api', 'Not Use API')],
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

    odoo_field_id = fields.Many2one(
        string='Odoo Field',
        comodel_name='ir.model.fields',
        ondelete='cascade',
        domain='[("model_id", "=", odoo_model_id)]',
        help='For simple fields you can select here field name from defined '
             'model to retrieve information from',
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
