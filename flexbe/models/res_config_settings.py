from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    config_flexbe_lead_type = fields.Selection(
        string='Flexbe Lead Type',
        config_parameter='flexbe.lead.type',
        selection=[
            ('lead', 'Lead'),
            ('opportunity', 'Opportunity'),
        ],
        default='lead',
        required=True,
    )
