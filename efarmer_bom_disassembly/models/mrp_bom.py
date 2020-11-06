from odoo import fields, models


class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    disassembly = fields.Boolean('Disassembly', default=False)
