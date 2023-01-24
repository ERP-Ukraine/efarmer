from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    zld_allowed_models = fields.Many2many(
        'ir.model',
        readonly=False,
        related='company_id.zld_allowed_models',
    )
