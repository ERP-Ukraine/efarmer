# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, _
from odoo.exceptions import UserError


class ExternalOrderFulfillment(models.Model):
    _name = 'external.order.fulfillment'
    _description = 'External Order Fulfillment'

    name = fields.Char(
        string='Name',
    )
    internal_status = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('skipped', 'Skipped'),
            ('failed', 'Failed'),
            ('done', 'Done'),
        ],
        string='Internal Status',
        default='draft',
        required=True,
    )
    external_str_id = fields.Char(
        string='External ID',
    )
    external_location_id = fields.Char(
        string='External Location ID',
    )
    external_status = fields.Char(
        string='External Status',
    )
    tracking_company = fields.Char(
        string='Tracking Company',
    )
    tracking_number = fields.Char(
        string='Tracking Number',
    )
    internal_info = fields.Char(
        string='Internal Info',
    )
    line_ids = fields.One2many(
        comodel_name='external.order.fulfillment.line',
        inverse_name='fulfillment_id',
        string='Lines',
    )
    erp_order_id = fields.Many2one(
        comodel_name='sale.order',
        string='ERP Order',
        ondelete='cascade',
    )
    integration_id = fields.Many2one(
        related='erp_order_id.integration_id',
    )
    do_cancel_external = fields.Boolean(
        string='Cancel Fulfillment',
        help='Technical field for cancel order flow only',
    )

    @property
    def is_done(self):
        return self.internal_status == 'done'

    def mark_done(self):
        self.write({
            'internal_status': 'done',
        })

    def mark_skipped(self):
        self.write({
            'internal_status': 'skipped',
        })

    def mark_failed(self):
        self.write({
            'internal_status': 'failed',
        })

    def validate(self):
        """
        Apply received order `fulfillment` in Odoo.
        It mean to perform `delivery validation`.

        :return: tuple(bool, int)
        """
        self.internal_info = False

        if self.is_done:
            return True, 0

        if self.erp_order_id.is_multi_stock and not self.erp_order_id.is_available_multi_stock_for_so:
            self.internal_info = _('Multiple locations feature for sales order is not available')
            self.mark_skipped()
            return False, 0

        if not self.erp_order_id.is_procurement_grouped:
            self.internal_info = _('Transfers were not grouped by warehouse')
            self.mark_skipped()
            return False, 0

        pickings = self._get_pickings()
        if not pickings:
            self.mark_done()
            return True, 0

        picking = pickings.filtered(lambda x: x._check_for_fulfill(self.line_ids))[:1]
        # TODO: what if the external fulfilment is suitable only for the pickings recordset
        if not picking:
            return False, 0

        try:
            result = picking._validate_external_fulfillment(self)
        except UserError as ex:
            self.internal_info = ex.args[0]
            self.mark_failed()
            result = False

        if result:
            picking.mark_integration_sent()
            self.mark_done()

        return result, picking.id

    def cancel_in_ecommerce_system(self):
        self.ensure_one()
        result = self.integration_id.adapter.cancel_fulfillment(self.external_str_id)
        if not result.get('userErrors'):
            self.external_status = 'cancelled'
        return result

    def _get_or_create_from_external(self, data):
        record = self.search([
            ('external_str_id', '=', data['external_str_id']),
            ('erp_order_id', '=', self._context.get('erp_order_id', False)),
        ], limit=1)

        lines = data.pop('lines', [])
        if not record:
            data['line_ids'] = [(0, 0, x) for x in lines]
            record = self.create(data)
        else:
            record.write(data)

        return record

    def _get_pickings(self):
        pickings = self.erp_order_id._get_pickings_to_handle()

        if self.erp_order_id.is_available_multi_stock_for_so:
            warehouse = self.integration_id._get_wh_from_external_location(self.external_location_id)
            if warehouse:
                pickings = pickings.filtered(lambda x: x.location_id.warehouse_id.id == warehouse.id)

        return pickings
