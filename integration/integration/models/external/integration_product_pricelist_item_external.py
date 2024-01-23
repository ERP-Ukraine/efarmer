# See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class IntegrationProductPricelistItemExternal(models.Model):
    _name = 'integration.product.pricelist.item.external'
    _description = 'Integration Product Pricelist Item External. Hide.'

    integration_id = fields.Many2one(
        comodel_name='sale.integration',
        required=True,
        ondelete='cascade',
    )
    template_id = fields.Many2one(
        comodel_name='product.template',
        string='Template',
        ondelete='cascade',
    )
    variant_id = fields.Many2one(
        comodel_name='product.product',
        string='Variant',
        ondelete='cascade',
    )
    item_id = fields.Many2one(
        comodel_name='product.pricelist.item',
        string='Pricelist Item',
        ondelete='cascade',
    )
    external_item_id = fields.Integer(
        string='External ID',
    )
