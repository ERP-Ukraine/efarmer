# -*- coding: UTF-8 -*-
# Copyright 2023 Solvve, Inc. <sales@solvve.com>

from typing import Dict
from hubspot.crm.deals import (
    SimplePublicObjectInput as DealInput,
)

from odoo import api, fields, models, _
from odoo.tools.safe_eval import safe_eval
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

    def _sale_order_field_map(self) -> Dict[str, str]:
        sale_order_field_map = self.env['ir.config_parameter'].sudo().get_param(
            'hubspot_quotation_connector.sale_order_field_map', '{}'
        )
        return safe_eval(sale_order_field_map)

    def _hubspot_field_convert(self, props: Dict) -> Dict:
        field_map = self._sale_order_field_map()
        return {
            field_map[key]: value
            for key, value in props.items()
            if key in field_map
        }

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
                'amount': float(deal.properties['amount']),
            } for deal in deal_items])

    def _update_deal(self, values: Dict):
        return self.hubspot_id._client.crm.deals.basic_api.update(
            deal_id=self.assigned_deal_object_id,
            simple_public_object_input=DealInput(
                properties=self._hubspot_field_convert(values)
            )
        )

    def assign(self):
        self.order_id.hubspot_deal_object_id = self.assigned_deal_object_id
        self._update_deal({
            'order_amount': self.order_id.amount_total,
            'order_margin': self.order_id.margin,
            'order_number': self.order_id.name,
        })
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
