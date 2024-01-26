# See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class IntegrationSaleOrderSubStatusMapping(models.Model):
    _name = 'integration.sale.order.sub.status.mapping'
    _inherit = 'integration.mapping.mixin'
    _description = 'Integration Sale Order Sub Status Mapping'
    _mapping_fields = ('odoo_id', 'external_id')

    odoo_id = fields.Many2one(
        comodel_name='sale.order.sub.status',
        ondelete='cascade',
    )

    external_id = fields.Many2one(
        comodel_name='integration.sale.order.sub.status.external',
        required=True,
        ondelete='cascade',
    )

    _sql_constraints = [
        (
            'uniq_mapping',
            'unique(integration_id, external_id)',
            'Sub-statuses mapping should be unique per integration'
        ),
    ]

    def import_statuses(self):
        status_external = self.mapped('external_id')

        if status_external:
            return status_external.import_statuses()
