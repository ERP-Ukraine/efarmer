#  See LICENSE file for full copyright and licensing details.

from ...shopify_api import SHOPIFY, METAFIELDS_NAME
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ProductEcommerceField(models.Model):
    _inherit = 'product.ecommerce.field'

    type_api = fields.Selection(
        selection_add=[(SHOPIFY, 'Shopify')],
        ondelete={
            SHOPIFY: 'cascade',
        },
    )

    shopify_metafield_type = fields.Selection(
        string=' Metafield Type',
        selection=[
            ('boolean', 'Boolean'),
            ('date', 'Date'),
            ('date_time', 'DateTime'),
            ('multi_line_text_field', 'Multi Line Text Field'),
            ('number_decimal', 'Number Decimal'),
            ('number_integer', 'Number Integer'),
            ('single_line_text_field', 'Single Line Text Field'),
        ]
    )

    @api.constrains('shopify_metafield_type', 'technical_name')
    def check_metafields(self):
        for record in self:
            if record.type_api == SHOPIFY:
                api_name = record.technical_name
                if api_name.find('.') == -1:
                    continue

                if len(api_name.split('.')) != 3 or not api_name.startswith(f'{METAFIELDS_NAME}.'):
                    raise ValidationError(_('Shopify Metafield must match to format '
                                            '"%s.<Namespace>.<Key>".') % METAFIELDS_NAME)

                if not record.shopify_metafield_type:
                    raise ValidationError(_('Please, select Metafield Type'))
