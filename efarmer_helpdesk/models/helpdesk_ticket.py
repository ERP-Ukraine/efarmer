from odoo import fields, models


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    efarmer_client_type = fields.Many2one(
        comodel_name='efarmer.client.type',
        string='Client Type',
        related='partner_id.efarmer_client_type',
        store=True,
    )
