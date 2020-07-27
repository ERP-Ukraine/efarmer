from odoo import fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    sale_state = fields.Selection(
        related='sale_id.state',
        string='Sale Status',
        readonly=False,
    )
