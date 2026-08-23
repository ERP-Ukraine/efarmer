# Copyright 2026 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import models

from hubspot.crm.tickets import SimplePublicObjectInput as TicketInput


class HubspotConnector(models.Model):
    _inherit = "hubspot.config"

    def create_ticket(self, ticket):
        """Create a HubSpot ticket from an Odoo helpdesk ticket.
            :return: the HubSpot ticket object id
        """
        self.ensure_one()
        hs_ticket = self._client.crm.tickets.basic_api.create(
            simple_public_object_input=TicketInput(
                properties={
                    "subject": ticket.name,
                    "content": ticket.description or "",
                    "odoo_rma": ticket.stage_id.name or "",
                    "odoo_status": ticket.name or "",
                    "hs_pipeline": "0",
                    "hs_pipeline_stage": "1",
                }
            )
        )
        ticket.write(
            {
                "hubspot_ticket_object_id": hs_ticket.id,
                "hubspot_synced": True,
            }
        )
        return hs_ticket.id

    def update_ticket(self, ticket):
        """Push the Odoo ticket's current name and stage to its HubSpot ticket."""
        self.ensure_one()
        self._client.crm.tickets.basic_api.update(
            ticket_id=ticket.hubspot_ticket_object_id,
            simple_public_object_input=TicketInput(
                properties={
                    "odoo_rma": ticket.name or "",
                    "odoo_status": ticket.stage_id.name or "",
                }
            )
        )
        return ticket.hubspot_ticket_object_id
