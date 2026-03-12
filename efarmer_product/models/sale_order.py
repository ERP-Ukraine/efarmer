# Copyright 2026 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    product_vat_id = fields.Many2one(
        comodel_name="product.vat",
        string="Product Vat",
    )

    is_auto_calc_taxes = fields.Boolean(
        default=lambda self: self._default_is_auto_calc_taxes(),
        string="Auto-calculate taxes",
    )

    helpdesk_ticket_count = fields.Integer(
        string="Tickets",
        compute="_compute_helpdesk_ticket_count",
    )

    @api.onchange("order_line")
    def _onchange_line_tax_id(self):
        if self.is_auto_calc_taxes:
            self.order_line.filtered(lambda r: not r.display_type)._compute_tax_ids()

    def action_view_helpdesk_tickets(self):
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "helpdesk.helpdesk_ticket_action_main_tree"
        )
        helpdesk_ticket_ids = self.env["helpdesk.ticket"].search(
            [("sale_order_id", "in", self.ids)]
        )
        action["domain"] = [("id", "in", helpdesk_ticket_ids.ids)]
        return action

    def _compute_helpdesk_ticket_count(self):
        for record in self:
            record.helpdesk_ticket_count = self.env["helpdesk.ticket"].search_count(
                [("sale_order_id", "=", record.id)]
            )

    @api.model
    def _default_is_auto_calc_taxes(self):
        """Return False if user has enabled the option, else company default"""
        user = self.env.user
        if getattr(user, "disable_so_tax_auto_calc", False):
            return False
        return getattr(self.env.company, "enable_so_tax_auto_calc", False)
