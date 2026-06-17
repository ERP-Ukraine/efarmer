from odoo import api, fields, models


class StockLot(models.Model):
    _inherit = "stock.lot"

    helpdesk_ticket_ids = fields.One2many(
        "helpdesk.ticket", "lot_id", "Helpdesk Tickets"
    )
    helpdesk_tickets_count = fields.Integer(
        "Helpdesk Tickets Count", compute="_compute_helpdesk_tickets_count"
    )

    @api.depends("helpdesk_ticket_ids")
    def _compute_helpdesk_tickets_count(self):
        for ticket in self:
            ticket.helpdesk_tickets_count = len(ticket.helpdesk_ticket_ids)

    def action_view_helpdesk_tickets(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Helpdesk Tickets",
            "res_model": "helpdesk.ticket",
            "view_mode": "list,form",
            "domain": [("id", "in", self.helpdesk_ticket_ids.ids)],
        }
