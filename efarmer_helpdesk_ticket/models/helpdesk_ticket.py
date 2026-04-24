# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    use_short_form = fields.Boolean(
        related="team_id.use_short_form", string="Short Form", store=True
    )
    allowed_tag_ids = fields.Many2many(
        comodel_name="helpdesk.tag",
        related="team_id.allowed_tag_ids",
        string="Allowed Tags",
    )
    note = fields.Char(string="Note")
    delivery_transfer_id = fields.Many2one(
        comodel_name="stock.picking", string="Delivery Transfer"
    )
    delivery_move_id = fields.Many2one(
        comodel_name="stock.move", string="Delivery Move"
    )
    scheduled_date = fields.Date(string="Scheduled date")
    returned_amount = fields.Float(string="Refund Amount (€)")

    @api.model
    def default_get(self, default_fields):
        values = super().default_get(default_fields)
        if self.env["helpdesk.team"].browse(values.get("team_id")).use_short_form:
            values["name"] = "Subject ..."
        return values

    def action_short_form(self):
        choose_product_by = (
            "serial"
            if not self.product_id
            or (self.product_id and self.product_id.tracking == "serial")
            else "other"
        )
        wizard = (
            self.env["short.ticket.form.wizard"]
            .with_context(choose_product_by=choose_product_by)
            .create(
                {
                    "ticket_id": self.id,
                    "choose_product_by": choose_product_by,
                    "allowed_tag_ids": [
                        (4, type) for type in self.team_id.allowed_tag_ids.ids
                    ],
                    "product_id": self.product_id.id,
                    "lot_id": self.lot_id.id,
                    "partner_id": self.partner_id.id,
                    "sale_id": self.sale_order_id.id,
                    "delivery_transfer_id": self.delivery_transfer_id.id,
                    "delivery_move_id": self.delivery_move_id.id,
                    "tag_ids": [(4, tag) for tag in self.tag_ids.ids],
                }
            )
        )
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "efarmer_helpdesk_ticket.short_ticket_action_view_form"
        )
        action["res_id"] = wizard.id
        action["context"] = {"choose_product_by": choose_product_by}
        return action
