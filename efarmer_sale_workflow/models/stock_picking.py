from odoo import fields, models, api


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    sale_state = fields.Selection(
        related='sale_id.state',
        string='Sale Status',
        readonly=False,
    )
    product_vat_id = fields.Many2one(
        related='sale_id.product_vat_id',
        string='VAT ID',
    )
    opportunity_stage_id = fields.Many2one(
        comodel_name='crm.stage',
        string='Opportunity Stage',
        related='sale_id.opportunity_id.stage_id',
        readonly=False,
    )
