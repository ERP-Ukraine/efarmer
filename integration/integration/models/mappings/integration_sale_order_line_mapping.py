# See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class IntegrationSaleOrderLineMapping(models.Model):
    _name = 'integration.sale.order.line.mapping'
    _inherit = 'integration.mapping.mixin'
    _description = 'Integration Sale Order Line Mapping'
    _mapping_fields = ('odoo_id', 'external_id')

    odoo_id = fields.Many2one(
        comodel_name='sale.order.line',
        ondelete='cascade',
    )

    external_id = fields.Many2one(
        comodel_name='integration.sale.order.line.external',
        required=True,
        ondelete='cascade',
    )
