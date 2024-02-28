# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'


    use_short_form = fields.Boolean(related='team_id.use_short_form', string='Short Form', store=True)

    @api.model
    def default_get(self, default_fields):
        values = super().default_get(default_fields)
        if self.env['helpdesk.team'].browse(values.get('team_id')).use_short_form:
            values['name'] = 'Subject ...'
        return values

    def action_short_form(self):
        wizard = self.env['short.ticket.form.wizard'].create({
            'ticket_id': self.id,
            'choose_product_by': 'serial' if not self.product_id or (self.product_id and self.product_id.tracking == 'serial') else 'other',
            'allowed_ticket_type_ids': [(4, type) for type in self.team_id.allowed_ticket_type_ids.ids],
            'product_id': self.product_id.id,
            'lot_id': self.lot_id.id,
            'partner_id': self.partner_id.id,
            'sale_id': self.sale_order_id.id,
            'type_id': self.ticket_type_id.id,
            'tag_ids': [(4,tag) for tag in self.tag_ids.ids],
        })
        action = self.env['ir.actions.act_window']._for_xml_id(
            'efarmer_helpdesk_ticket.short_ticket_action_view_form'
        )
        action['res_id'] = wizard.id
        return action
