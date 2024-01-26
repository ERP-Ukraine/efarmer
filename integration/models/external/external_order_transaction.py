# See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class ExternalOrderTransaction(models.Model):
    _name = 'external.order.transaction'
    _description = 'External Order Transaction'

    external_str_id = fields.Char(
        string='External ID',
    )
    external_parent_str_id = fields.Char(
        string='Parent ID',
    )
    external_order_str_id = fields.Char(
        string='External Order ID',
    )
    amount = fields.Char(
        string='Amount',
    )
    currency = fields.Char(
        string='Currency',
    )
    gateway = fields.Char(
        string='Gateway',
    )
    erp_order_id = fields.Many2one(
        comodel_name='sale.order',
        string='ERP Order',
        ondelete='cascade',
    )
    integration_id = fields.Many2one(
        comodel_name='sale.integration',
        related='erp_order_id.integration_id',
        store=True,
    )

    def _get_or_create_txn_from_external(self, data):
        record = self.search([
            ('external_str_id', '=', str(data['id'])),
            ('external_order_str_id', '=', str(data['order_id'])),
            ('integration_id', '=', self._context.get('integration_id', False)),
        ], limit=1)

        if not record:
            vals = self._prepare_vals_from_external(data)
            record = self.create(vals)

        return record

    def _prepare_vals_from_external(self, data):
        vals = dict(
            amount=data['amount'],
            gateway=data['gateway'],
            currency=data['currency'],
            external_str_id=str(data['id']),
            external_order_str_id=str(data['order_id']),
            external_parent_str_id=str(data.get('parent_id') or ''),
        )
        return vals
