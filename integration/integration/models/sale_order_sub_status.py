# See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class SaleOrderSubStatus(models.Model):
    _name = 'sale.order.sub.status'
    _description = 'Sale Order Sub Status'
    _inherit = ['integration.model.mixin']
    _internal_reference_field = 'code'

    name = fields.Char(
        string='Name',
        help='Here we will have user friendly name of the order status',
        required=True,
        translate=True,
    )

    code = fields.Char(
        string='Order Status Code',
        help='In case it is possible - we will be able to insert here order status code, '
             'to uniquely identify order code',
    )

    integration_id = fields.Many2one(
        comodel_name='sale.integration',
        ondelete='cascade',
    )

    def unlink(self):
        # Delete all external statuses also
        if not self.env.context.get('skip_other_delete', False):
            sub_status_mapping_model = self.env['integration.sale.order.sub.status.mapping']
            for odoo_status in self:
                sub_statuses_mappings = sub_status_mapping_model.search([
                    ('odoo_id', '=', odoo_status.id)
                ])
                for mapping in sub_statuses_mappings:
                    mapping.external_id.with_context(skip_other_delete=True).unlink()
        return super(SaleOrderSubStatus, self).unlink()
