# -*- coding: UTF-8 -*-
# Copyright 2023 Solvve, Inc. <sales@solvve.com>

from odoo import api, fields, models, _
from odoo.tools.safe_eval import safe_eval
from odoo.addons.hubspot_quotation_connector.fields import BigInteger


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    hubspot_deal_object_id = BigInteger()

    @api.model_create_multi
    def create(self, vals):
        order_ids = super(SaleOrder, self).create(vals)
        order_ids._update_hubspot_field()
        return order_ids

    def write(self, values):
        response = super(SaleOrder, self).write(values)
        self._update_hubspot_field()
        return response

    def _update_hubspot_field(self):
        hubspot_id = self.env[self._name]._get_hubspot_id()
        now_timestamp = hubspot_id.datetime_parse(fields.Datetime.now())
        for order_id in self:
            if order_id.state != 'sale':
                continue
            hubspot_id.update_deal(
                deal_object_id=order_id.hubspot_deal_object_id,
                values={'order_date': now_timestamp},
            )

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
            return {
                'warning': {
                    'title': _("Warning!"),
                    'message': _('HubSpot is not active'),
                }
            }
        action['context'] = {
            **safe_eval(action['context']),
            'default_order_id': self.id,
            'default_hubspot_id': hubspot_id.id
        }
        return action
