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

    integration_sale_channel_id = fields.Many2one(
        string='e-Commerce Sales Channel',
        comodel_name='external.sale.channel',
        copy=False,
        help=(
            'The specific sales channel (e.g., Online Store, POS, Facebook) where this Shopify order originated.'
        ),
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

    def _integration_validate_order(self):
        result, message = super()._integration_validate_order()

        if not result:
            return result, message

        if self.integration_id.is_shopify():
            _logger.info('Run integration auto-workflow validate_order: Shopify overridden')
            if self.integration_id.apply_external_fulfillments:

                for fulfillment in self.external_fulfillment_ids.filtered(lambda x: not x.is_done):
                    res, __ = fulfillment.validate()

                    if not res:
                        _logger.warning(
                            '%s: %s --> External fulfillment "%s" was not applied',
                            self.integration_id.name, self, fulfillment.external_str_id,
                        )

        return result, message

    def _adjust_integration_external_data(self, external_data):
        if not self.integration_id.is_shopify():
            return super(SaleOrder, self)._adjust_integration_external_data(external_data)

        external_order_id = self.env.context.get('external_order_id')
        if not external_order_id:
            return external_data

        adapter = self.integration_id.adapter
        if 'order_risks' not in external_data:
            # 1. Fetch Order Risks
            order_risks = adapter.fetch_order_risks(external_order_id)
            external_data['order_risks'] = order_risks

        if 'order_transactions' not in external_data:
            # 2. Fetch Order Payments
            order_txns = adapter.fetch_order_payments(external_order_id)
            external_data['order_transactions'] = order_txns

        if 'order_fulfillments' not in external_data:
            # 3. Fetch Order Fulfillments
            order_fulfillments = adapter.fetch_fulfillments(external_order_id)
            external_data['order_fulfillments'] = order_fulfillments

        return external_data

    def _apply_values_from_external(self, external_data):
        if not self.integration_id.is_shopify():
            return super(SaleOrder, self)._apply_values_from_external(external_data)

        if not isinstance(external_data, dict):
            return external_data

        vals = dict()
        # 0. State update
        if external_data.get('integration_workflow_states'):
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
            vals.update(
                sub_status_id=sub_status_financial.id,
                shopify_fulfilment_status=sub_status_fulfillment.id,
            )

        # 1. Tags
        if external_data.get('external_tags'):
            # 2. Update Tags
            ctx = dict(default_integration_id=self.integration_id.id)
            ExternalTag = self.env['external.integration.tag'].with_context(**ctx)

            tags = list()
            for tag_name in external_data['external_tags']:
                tag = ExternalTag._get_or_create_tag_from_name(tag_name)
                tags.append((4, tag.id, 0))

            vals['external_tag_ids'] = tags

        # 2. Risks
        if external_data.get('order_risks'):
            # 3. Update Risks
            ExternalOrderRisk = self.env['external.order.risk']

            risks = list()
            for risk_data in external_data['order_risks']:
                risk = ExternalOrderRisk._create_or_update_risk_from_external(risk_data)
                risk.append((4, risk.id, 0))

            vals['order_risk_ids'] = risks

        # 3. Payment
        if external_data.get('order_transactions'):
            # 4. Update Transactions (Payments)
            Transaction = self.env['external.order.transaction']\
                .with_context(integration_id=self.integration_id.id)

            txns = list()
            for txn_data in external_data['order_transactions']:
                txn = Transaction._get_or_create_txn_from_external(txn_data)
                txns.append((4, txn.id, 0))

            vals['external_payment_ids'] = txns

        # 4. Fulfillments
        if external_data.get('order_fulfillments'):
            Fulfillment = self.env['external.order.fulfillment']\
                .with_context(erp_order_id=self.id)

            fulfillments = list()
            for fulfill_data in external_data['order_fulfillments']:
                record = Fulfillment._get_or_create_from_external(fulfill_data)
                fulfillments.append((4, record.id, 0))

            vals['external_fulfillment_ids'] = fulfillments

        if vals:
            self.with_context(skip_dispatch_to_external=True).write(vals)

        # -- Post actions -- TODO: this actions have to by process by workflow tasks (integration.workflow.pipeline)
        if self.env.context.get('skip_integration_order_post_action'):
            return external_data

        if self.is_confirmed:
            # 4.1 Apply fulfillments
            if self.integration_id.apply_external_fulfillments:
                for record in self.external_fulfillment_ids.filtered(lambda x: not x.is_done):
                    record.validate()

        return external_data

    def _get_order_fraud_threshold(self):
        threshold = self.env['ir.config_parameter'].sudo().get_param(
            'integration.fraud_threshold',
        )
        return float(threshold)
