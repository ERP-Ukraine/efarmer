from odoo import api, fields, models
from odoo.exceptions import UserError


class MailMessage(models.Model):
    _inherit = "mail.message"

    lead_id = fields.Many2one(
        "crm.lead", "Lead / Opportunity", compute="_compute_links"
    )
    ticket_id = fields.Many2one(
        "helpdesk.ticket", "Helpdesk Ticket", compute="_compute_links"
    )

    def _compute_links(self):
        for message in self:
            message.lead_id = False
            message.ticket_id = False

            if message.model == "crm.lead" and message.res_id:
                message.lead_id = message.res_id
            elif message.model == "helpdesk.ticket":
                message.ticket_id = message.res_id

    @api.model
    def action_open_conv_history(self, model_tech_name):
        if model_tech_name not in ("crm.lead", "helpdesk.ticket"):
            raise UserError("Appliable for leads and tickets only.")

        list_view = self.env.ref(
            "efarmer_conversation_history.mail_message_view_tree_conv_history"
        )
        form_view = self.env.ref(
            "efarmer_conversation_history.mail_message_view_form_conv_history"
        )
        search_view = self.env.ref(
            "efarmer_conversation_history.mail_message_search_form_conv_history"
        )
        discussions = self.env.ref("mail.mt_comment")
        note = self.env.ref("mail.mt_note")

        domain = [
            "|",
            "&",
            ("message_type", "=", "comment"),
            ("subtype_id", "in", (discussions.id, note.id)),
            ("message_type", "=", "email"),
            ("model", "=", model_tech_name),
        ]

        return {
            "type": "ir.actions.act_window",
            "name": "Conversations History",
            "res_model": "mail.message",
            "views": [(list_view.id, "list"), (form_view.id, "form")],
            "search_view_id": search_view.id,
            "domain": domain,
        }

    def action_open_conv_doc(self):
        self.ensure_one()
        if self.lead_id:
            return self.lead_id.redirect_lead_opportunity_view()
        elif self.ticket_id:
            return {
                "type": "ir.actions.act_window",
                "name": self.ticket_id.name,
                "res_model": "helpdesk.ticket",
                "view_mode": "form",
                "res_id": self.ticket_id.id,
            }
