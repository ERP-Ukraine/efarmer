# See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class IntegrationSaleOrderMapping(models.Model):
    _name = 'integration.sale.order.mapping'
    _inherit = 'integration.mapping.mixin'
    _description = 'Integration Sale Order Mapping'
    _mapping_fields = ('odoo_id', 'external_id')

    odoo_id = fields.Many2one(
        comodel_name='sale.order',
        ondelete='cascade',
    )

    external_id = fields.Many2one(
        comodel_name='integration.sale.order.external',
        required=True,
        ondelete='cascade',
    )
