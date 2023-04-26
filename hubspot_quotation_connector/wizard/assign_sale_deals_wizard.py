# -*- coding: UTF-8 -*-
# Copyright 2023 Solvve, Inc. <sales@solvve.com>

import logging
from odoo import api, fields, models, _
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT as DATETIME_FORMAT
from odoo.addons.hubspot_quotation_connector.fields import BigInteger

_logger = logging.getLogger(__name__)


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

    def _get_fetch_limit(self, default: int = 40) -> int:
        fetch_limit = self.env['ir.config_parameter'].sudo().get_param(
            key='hubspot_quotation_connector.deals_fetch_limit',
            default=default,
        )
        try:
            return int(fetch_limit)
        except Exception as ex:
            _logger.warning(_(
                'Incorrect value in parameter "%s".\n%s',
                'hubspot_quotation_connector.deals_fetch_limit',
                str(ex)
            ))
            return default

    @api.depends('hubspot_id')
    def _compute_deal_ids(self):
        create_deal_line = self.env['assign.sale.deals.line.wizard'].create
        fetch_limit = self._get_fetch_limit()
        for assign_id in self:
            hubspot_id = assign_id.hubspot_id
            if not hubspot_id:
                assign_id.deal_ids = None
                continue
            partner_id = assign_id.order_id.partner_id
            deal_items = hubspot_id.get_deals_by_partner(partner_id, limit=fetch_limit)
            if not deal_items:
                assign_id.deal_ids = None
                continue
            assign_id.deal_ids = create_deal_line([{
                'name': deal.properties['dealname'],
                'deal_object_id': int(deal.id),
                'amount': float(deal.properties['amount'] or 0),
                'deal_createdate': deal.created_at.strftime(DATETIME_FORMAT),
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
        return self.hubspot_id.notification(_('Successfully assigned'))


class AssignSaleDealsLineWizard(models.TransientModel):
    _name = 'assign.sale.deals.line.wizard'
    _description = 'Assign Sale Deals Line Wizard'

    name = fields.Char(required=True)
    amount = fields.Float(store=True)
    deal_object_id = BigInteger(required=True)
    deal_createdate = fields.Datetime()

    def name_get(self):
        response = []
        for line_id in self:
            name = '; '.join(item for item in [
                line_id.name,
                f'Amount: {line_id.amount}' if line_id.amount else None
            ] if item)
            response.append((line_id.id, name))
        return response
