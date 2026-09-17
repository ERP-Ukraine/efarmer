# Copyright 2026 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import _, fields, models


class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    hubspot_ticket_object_id = fields.Char(
        string="HubSpot Ticket ID",
        copy=False,
        readonly=True,
    )
    hubspot_synced = fields.Boolean(
        string="Synced with HubSpot",
        default=False,
        copy=False,
        readonly=True,
    )

    def _get_hubspot_id(self):
        param = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("hubspot_quotation_connector.sale_hubspot_config_id")
        )
        if not param:
            return self.env["hubspot.config"]
        return self.env["hubspot.config"].browse(int(param)).exists()

    def _active_hubspot_connector(self):
        param = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("hubspot_quotation_connector.use_sale_hubspot_connector")
        )
        return param in ("True", "true", "1", 1, True)

    def action_sync_hubspot_ticket(self):
        self.ensure_one()
        hubspot_id = self._get_hubspot_id()
        if not (self._active_hubspot_connector() and hubspot_id):
            return hubspot_id.notification(_("Is not active"), "warning")
        if self.hubspot_ticket_object_id:
            return hubspot_id.notification(_("Already synced"), "warning")
        hubspot_id.create_ticket(self)
        return hubspot_id.notification(_("Successfully synced"))

    def write(self, vals):
        res = super().write(vals)
        if "stage_id" in vals and not self.env.context.get("skip_hubspot_sync"):
            if not self._active_hubspot_connector():
                return res
            hubspot_id = self._get_hubspot_id()
            if hubspot_id:
                for ticket in self:
                    if ticket.hubspot_ticket_object_id:
                        hubspot_id.update_ticket(ticket)
        return res
