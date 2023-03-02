# -*- coding: UTF-8 -*-
# Copyright 2023 Solvve, Inc. <sales@solvve.com>

from odoo import api, fields, models, _
from odoo.addons.hubspot_quotation_connector.fields import BigInteger


class AssignSaleDealsWizard(models.TransientModel):
    _name = 'assign.sale.deals.wizard'
    _description = 'Assign Deals with Sale Order'

    order_id = fields.Many2one(
        comodel_name='sale.order',
        required=True,
    )
    hubspot_id = fields.Many2one(
        comodel_name='hubspot.config',
        required=True,
    )
    assigned_deal_id = fields.Many2one(
        comodel_name='assign.sale.deals.line.wizard',
        required=True,
    )
    assigned_deal_object_id = BigInteger(related='assigned_deal_id.deal_object_id')
    deal_ids = fields.One2many(
        comodel_name='assign.sale.deals.line.wizard',
        compute='_compute_deal_ids',
    )

    @api.depends('hubspot_id')
    def _compute_deal_ids(self):
        create_deal_line = self.env['assign.sale.deals.line.wizard'].create
        for assign_id in self:
            hubspot_id = assign_id.hubspot_id
            if not hubspot_id:
                assign_id.deal_ids = None
                continue
            partner_id = assign_id.order_id.partner_id
            deal_items = hubspot_id.get_deals_by_partner(partner_id)
            if not deal_items:
                assign_id.deal_ids = None
                continue
            assign_id.deal_ids = create_deal_line([{
                'name': deal.properties['dealname'],
                'deal_object_id': int(deal.id),
                'amount': float(deal.properties['amount'] or 0),
            } for deal in deal_items])

    def assign(self):
        self.order_id.write({
            'hubspot_deal_name': self.assigned_deal_id.name,
            'hubspot_deal_object_id': self.assigned_deal_object_id,
        })
        self.hubspot_id.update_deal(
            deal_object_id=self.assigned_deal_object_id,
            values={
                'order_amount': self.order_id.amount_total,
                'order_margin': self.order_id.margin,
                'order_number': self.order_id.name,
            }
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('HubSpot'),
                'message': _('Successfully assigned'),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }


class AssignSaleDealsLineWizard(models.TransientModel):
    _name = 'assign.sale.deals.line.wizard'
    _description = 'Assign Sale Deals Line Wizard'

    name = fields.Char(required=True)
    amount = fields.Float(store=True)
    deal_object_id = BigInteger(required=True)

    def name_get(self):
        response = []
        for line_id in self:
            name = '; '.join(item for item in [
                line_id.name,
                f'Amount: {line_id.amount}' if line_id.amount else None
            ] if item)
            response.append((line_id.id, name))
        return response
