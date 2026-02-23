from odoo import models, fields


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    partner_id = fields.Many2one(related="picking_id.partner_id", string="Customer", store=True)
