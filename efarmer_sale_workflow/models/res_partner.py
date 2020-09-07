from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    efarmer_client_type = fields.Many2one('efarmer.client.type', 'Client Type')
