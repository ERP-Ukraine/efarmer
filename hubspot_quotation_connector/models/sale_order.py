# -*- coding: UTF-8 -*-
# Copyright 2023 Solvve, Inc. <sales@solvve.com>

from hubspot.crm.deals.models import (
    BatchInputSimplePublicObjectBatchInput as DealsBatchInput
)

from odoo import api, fields, models, _
from odoo.tools.safe_eval import safe_eval
from odoo.addons.hubspot_quotation_connector.fields import BigInteger


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    hubspot_deal_object_id = BigInteger()
    hubspot_deal_name = fields.Char()

    @api.model_create_multi
    def create(self, vals):
        order_ids = super(SaleOrder, self).create(vals)
        order_ids.filtered(lambda order: order.state == 'sale')._update_hubspot_field()
        return order_ids

    def write(self, values):
        response = super(SaleOrder, self).write(values)
        if values.get('state') == 'sale':
            self._update_hubspot_field()
        return response

    def _update_hubspot_field(self):
        if not self:
            return None
        if not self._active_hubspot_connector():
            return None
        hubspot_id = self.env[self._name]._get_hubspot_id()
        if not hubspot_id:
            return None
        now_timestamp = hubspot_id.datetime_parse(fields.Datetime.now())
        inputs = [{
            'id': order_id.hubspot_deal_object_id,
            'properties': hubspot_id._hubspot_field_convert({
                'order_date': now_timestamp
            })
        } for order_id in self if order_id.hubspot_deal_object_id]
        if inputs:
            hubspot_id._client.crm.deals.batch_api.update(DealsBatchInput(inputs))

    def _active_hubspot_connector(self) -> bool:
        get_param = self.env['ir.config_parameter'].sudo().get_param
        return bool(get_param('hubspot_quotation_connector.use_sale_hubspot_connector'))

    @api.model
    def _get_hubspot_id(self) -> 'odoo.model.hubspot_config':
        get_param = self.env['ir.config_parameter'].sudo().get_param
        hubspot = get_param('hubspot_quotation_connector.sale_hubspot_config_id')
        config_env = self.env['hubspot.config']
        if not hubspot:
            return config_env
        return config_env.browse(int(hubspot))

    def action_assign_hubspot_deal(self):
        action_xmlid = 'hubspot_quotation_connector.assign_hubspot_deals_wizard_act_window'
        action = self.env['ir.actions.actions']._for_xml_id(action_xmlid)
        hubspot_id = self._get_hubspot_id()
        if not (self._active_hubspot_connector() and hubspot_id):
            return hubspot_id.notification(_('Is not active'), 'warning')
        action['context'] = {
            **safe_eval(action['context']),
            'default_order_id': self.id,
            'default_hubspot_id': hubspot_id.id
        }
        return action

    def action_unassign_hubspot_deal(self):
        if not self.hubspot_deal_object_id:
            return None
        hubspot_id = self._get_hubspot_id()
        if not (self._active_hubspot_connector() and hubspot_id):
            return hubspot_id.notification(_('Is not active'), 'warning')
        if not hubspot_id:
            return hubspot_id.notification(_('Is not active'), 'warning')
        hubspot_id.update_deal(self.hubspot_deal_object_id, {'order_number': ''})
        self.write({
            'hubspot_deal_object_id': None,
            'hubspot_deal_name': '',
        })
        return hubspot_id.notification(_('Successfully unassigned'))
