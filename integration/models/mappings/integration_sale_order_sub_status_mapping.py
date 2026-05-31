# See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class IntegrationSaleOrderSubStatusMapping(models.Model):
    _name = 'integration.sale.order.sub.status.mapping'
    _inherit = 'integration.mapping.mixin'
    _description = 'External Order Status Mapping'
    _mapping_fields = ('odoo_id', 'external_id')
    _mapping_label = 'Order Status'

    odoo_id = fields.Many2one(
        string='Odoo E-Commerce Order Status',
        comodel_name='sale.order.sub.status',
        ondelete='set null',
    )

    external_id = fields.Many2one(
        string='External Order Status',
        comodel_name='integration.sale.order.sub.status.external',
        required=True,
        ondelete='cascade',
    )

    _uniq_mapping = models.Constraint(
        'unique(integration_id, external_id)',
        'External order statuses should be unique per store',
    )

    def import_statuses(self):
        status_external = self.mapped('external_id')

        if status_external:
            return status_external.import_statuses()
