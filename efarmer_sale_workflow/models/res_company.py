from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    additional_vat_note = fields.Boolean(
        string='Show Additional Vat Note',
        help='Vat Directives of EC',
    )
