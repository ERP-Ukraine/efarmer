from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    opportunity_stage_id = fields.Many2one(
        comodel_name='crm.stage',
        string='Opportunity Stage',
        related='opportunity_id.stage_id',
        readonly=False,
    )
