# See LICENSE file for full copyright and licensing details.

import logging

from odoo import models, fields, api, _


_logger = logging.getLogger(__name__)

_RISK_PRIORITY = {'high': 3, 'medium': 2, 'low': 1, 'pending': 0, 'none': -1}


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
    shopify_risk_level = fields.Selection(
        selection=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('pending', 'Pending'),
            ('none', 'None')
        ],
        string='Shopify Risk Level',
        compute='_compute_shopify_risk',
        store=True,
    )
    shopify_risk_recommendation = fields.Selection(
        selection=[
            ('accept', 'Accept'),
            ('investigate', 'Investigate'),
            ('cancel', 'Cancel'),
            ('none', 'No Recommendation'),
        ],
        string='Shopify Risk',
        compute='_compute_shopify_risk',
        store=True,
    )

    integration_sale_channel_id = fields.Many2one(
        string='E-Commerce Sales Channel',
        comodel_name='external.sale.channel',
        copy=False,
        help=(
            'The specific sales channel (e.g., Online Store, POS, Facebook) where this Shopify order originated.'
        ),
    )

    integration_order_source_name_id = fields.Many2one(
        string='E-Commerce Order Source Name',
        comodel_name='external.order.source.name',
        copy=False,
        help=(
            'The name of the source associated with the order.'
        ),
    )

    payment_method_ids = fields.Many2many(
        string='E-Commerce Payment Methods',
        comodel_name='sale.order.payment.method',
        domain='[("integration_id", "=", integration_id)]',
        copy=False,
    )

    external_tag_ids = fields.Many2many(
        string='External Tags',
        comodel_name='external.integration.tag',
        relation='external_integration_tag_sale_order_rel',
        column1='sale_order_id',
        column2='external_integration_tag_id',
        domain='[("ttype", "=", "order")]',
        copy=False,
    )

    def _shopify_cancel_order(self, *args, **kw):
        # from _perform_method_by_name calling
        _logger.info('SaleOrder _shopify_cancel_order(). Not implemented.')
        pass

    def _shopify_shipped_order(self, *args, **kw):
        # from _perform_method_by_name calling
        _logger.info('SaleOrder _shopify_shipped_order(). Not implemented.')
        pass

    def _shopify_paid_order(self, *args, **kw):
        # from _perform_method_by_name calling
        _logger.info('SaleOrder _shopify_paid_order()')

        status = self.env['sale.order.sub.status'].from_external(self.integration_id, 'paid')
        self.sub_status_id = status.id

    def action_view_order_risks(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Order Risk Details'),
            'res_model': 'external.order.risk',
            'view_mode': 'list,form',
            'views': [
                (self.env.ref('integration_shopify.external_order_risk_view_list_readonly').id, 'list'),
                (self.env.ref('integration_shopify.external_order_risk_view_form').id, 'form'),
            ],
            'domain': [('erp_order_id', '=', self.id)],
            'target': 'new',
            'context': {'create': False, 'edit': False, 'delete': False},
        }

    @api.depends('order_risk_ids.risk_level', 'order_risk_ids.recommendation')
    def _compute_shopify_risk(self):
        for rec in self:
            risks = rec.order_risk_ids
            if not risks:
                rec.shopify_risk_level = False
                rec.shopify_risk_recommendation = False
            else:
                highest = max(risks, key=lambda r: _RISK_PRIORITY.get(r.risk_level, 0))
                rec.shopify_risk_level = highest.risk_level
                rec.shopify_risk_recommendation = highest.recommendation

    @api.depends('order_risk_ids')
    def _compute_is_risky_sale(self):
        for rec in self:
            rec.is_risky_sale = bool(
                rec.order_risk_ids.filtered(
                    lambda x: x.recommendation in ('cancel', 'investigate')
                )
            )

    def _adjust_integration_external_data(self, external_data: dict) -> dict:
        # Perform the common logic in the super() method
        res = super(SaleOrder, self)._adjust_integration_external_data(external_data)

        if not self.integration_id.is_integration_shopify:
            return res

        external_order_id = self.external_order_name
        adapter = self.integration_id.adapter

        order = adapter.gql.Order.set(id=external_order_id)
        order.update_props(
            use_customer_currency=adapter._settings['use_customer_currency'],
        )
        read_order = False

        def _read():
            nonlocal read_order

            if not read_order:
                order.read()
                read_order = True

        if 'order_risks' not in external_data:
            # 1. Fetch Order Risks
            _read()
            order_risks = order.parse_order_risks()
            external_data['order_risks'] = order_risks

        if 'payment_transactions' not in external_data:
            # 2. Fetch Order Payments
            _read()
            payment_txns = order.parse_payment_transactions()
            external_data['payment_transactions'] = payment_txns

        if 'order_fulfillments' not in external_data:
            # 3. Fetch Order Fulfillments
            _read()
            order_fulfillments = order.parse_fulfillments()
            external_data['order_fulfillments'] = order_fulfillments

        return external_data

    def _apply_values_from_external(self, external_data: dict) -> dict:
        integration = self.integration_id

        if integration.is_integration_shopify:
            vals = dict()
            # 0. State update --> partially updated in the super() method
            if external_data.get('integration_workflow_states'):
                # 1. Update Statuses
                fulfillment_code = external_data['integration_workflow_states'][1]

                sub_status_fulfillment = integration._get_order_sub_status(fulfillment_code)

                vals['shopify_fulfilment_status'] = sub_status_fulfillment.id

            # 1. Tags
            if external_data.get('external_tags'):
                # 2. Update Tags
                tags = []
                for tag_name in external_data['external_tags']:
                    tag = self.env['external.integration.tag'] \
                        ._get_or_create_external_tag(tag_name, 'order', integration_id=integration.id)
                    tags.append((4, tag.id, 0))

                vals['external_tag_ids'] = tags

            # 2. Risks
            if 'order_risks' in external_data:
                # 3. Update Risks: clear existing and replace with latest data from Shopify
                ExternalOrderRisk = self.env['external.order.risk']
                risks = [(5, 0, 0)]
                for risk_data in external_data['order_risks']:
                    vals_risk = ExternalOrderRisk._prepare_vals_from_external(risk_data)
                    risks.append((0, 0, vals_risk))

                vals['order_risk_ids'] = risks

            # 3. Fulfillments
            if external_data.get('order_fulfillments'):
                Fulfillment = self.env['external.order.fulfillment'] \
                    .with_context(integration_id=integration.id)

                fulfillments = list()
                for fulfill_data in external_data['order_fulfillments']:
                    record = Fulfillment._get_or_create_from_external(fulfill_data)
                    fulfillments.append((4, record.id, 0))

                vals['external_fulfillment_ids'] = fulfillments

            if vals:
                self.with_context(skip_dispatch_to_external=True).write(vals)

        return super(SaleOrder, self)._apply_values_from_external(external_data)
