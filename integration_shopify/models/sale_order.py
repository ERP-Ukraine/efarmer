# See LICENSE file for full copyright and licensing details.

import logging

from odoo import models, fields, api


_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    is_risky_sale = fields.Boolean(
        string='Risky Order',
        compute='_compute_is_risky_sale',
        store=True,
    )
    order_risk_ids = fields.One2many(
        comodel_name='external.order.risk',
        inverse_name='erp_order_id',
        string='Risks',
        copy=False,
    )
    shopify_fulfilment_status = fields.Many2one(
        string='Shopify Fulfillment Status',
        comodel_name='sale.order.sub.status',
        domain='[("integration_id", "=", integration_id)]',
        ondelete='set null',
        tracking=True,
        copy=False,
    )

    def _shopify_cancel_order(self, *args, **kw):
        _logger.info('SaleOrder _shopify_cancel_order(). Not implemented.')
        pass

    def _shopify_shipped_order(self, *args, **kw):
        _logger.info('SaleOrder _shopify_shipped_order(). Not implemented.')
        pass

    def _shopify_paid_order(self, *args, **kw):
        _logger.info('SaleOrder _shopify_paid_order()')
        status = self.env['sale.order.sub.status']\
            .from_external(self.integration_id, 'paid')  # TODO: attention, hardcode!
        self.sub_status_id = status.id

    def _prepare_vals_for_sale_order_status(self):
        res = super(SaleOrder, self)._prepare_vals_for_sale_order_status()
        if self.integration_id.is_shopify():
            res['amount'] = str(self.amount_total)
            res['currency'] = self.currency_id.name
        return res

    @api.depends('order_risk_ids')
    def _compute_is_risky_sale(self):
        threshold = self._get_order_fraud_threshold()

        for rec in self:
            order_risk_ids = rec.order_risk_ids

            if order_risk_ids.filtered(lambda x: x.recommendation == 'cancel'):
                value = True
            elif order_risk_ids.filtered(lambda x: float(x.score) > threshold):
                value = True
            else:
                value = False

            rec.is_risky_sale = value

    def _apply_so_status_external_data(self, external_data):
        if not self.integration_id.is_shopify():
            return super(SaleOrder, self)._apply_so_status_external_data(external_data)

        Transaction = self.env['external.order.transaction']\
            .with_context(integration_id=self.integration_id.id)

        if not all(external_data):  # (result: bool, dict_object: dict) = external_data
            return Transaction

        __, txn_data = external_data
        txn_id = Transaction._get_or_create_txn_from_external(txn_data)
        self.external_payment_ids = [(4, txn_id.id, 0)]
        return txn_id

    def _adjust_integration_external_data(self, external_data):
        if not self.integration_id.is_shopify():
            return super(SaleOrder, self)._adjust_integration_external_data(external_data)

        external_order_id = self.env.context.get('external_order_id')
        if not external_order_id:
            return external_data

        adapter = self.integration_id.adapter
        # 1. Fetch Order Risks
        order_risks = adapter.fetch_order_risks(external_order_id)
        external_data['order_risks'] = order_risks

        # 2. Fetch Order Payments
        order_txns = adapter.fetch_order_payments(external_order_id)
        external_data['order_transactions'] = order_txns
        return external_data

    def _apply_values_from_external(self, external_data):
        if not self.integration_id.is_shopify():
            return super(SaleOrder, self)._apply_values_from_external(external_data)

        # 1. Update Statuses
        SoFactory = self.env['integration.sale.order.factory']
        financial_code, fulfillment_code = external_data['integration_workflow_states']

        sub_status_financial = SoFactory._get_order_sub_status(
            self.integration_id,
            financial_code,
        )
        sub_status_fulfillment = SoFactory._get_order_sub_status(
            self.integration_id,
            fulfillment_code,
        )
        # 2. Update Tags
        ctx = dict(default_integration_id=self.integration_id.id)
        ExternalTag = self.env['external.integration.tag'].with_context(**ctx)
        tag_ids = ExternalTag.browse()

        for tag_name in external_data.get('external_tags', []):
            tag_id = ExternalTag._get_or_create_tag_from_name(tag_name)
            tag_ids |= tag_id

        # 3. Update Risks
        ExternalOrderRisk = self.env['external.order.risk']
        risk_ids = ExternalOrderRisk.browse()

        for risk_data in external_data.get('order_risks', []):
            risk_ids |= ExternalOrderRisk._create_or_update_risk_from_external(risk_data)

        # 4. Update Transactions (Payments)
        Transaction = self.env['external.order.transaction']\
            .with_context(integration_id=self.integration_id.id)
        txn_ids = Transaction.browse()

        for txn_data in external_data.get('order_transactions', []):
            txn_ids |= Transaction._get_or_create_txn_from_external(txn_data)

        vals = dict(
            order_risk_ids=[(6, 0, risk_ids.ids)],
            sub_status_id=sub_status_financial.id,
            external_tag_ids=[(6, 0, tag_ids.ids)],
            external_payment_ids=[(6, 0, txn_ids.ids)],
            shopify_fulfilment_status=sub_status_fulfillment.id,
        )
        return self.with_context(skip_dispatch_to_external=True).write(vals)

    def _get_order_fraud_threshold(self):
        threshold = self.env['ir.config_parameter'].sudo().get_param(
            'integration.fraud_threshold',
        )
        return float(threshold)
