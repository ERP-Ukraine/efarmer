from odoo import fields, models, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    additional_vat_note = fields.Boolean(
        related='company_id.additional_vat_note',
        string='Show Additional Vat Note',
        help='Vat Directives of EC',
        readonly=False,
    )
