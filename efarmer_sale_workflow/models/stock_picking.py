from odoo import fields, models, api


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    sale_state = fields.Selection(
        related='sale_id.state',
        string='Sale Status',
        readonly=False,
    )
    opportunity_stage_id = fields.Many2one(
        comodel_name='crm.stage',
        string='Opportunity Stage',
        related='sale_id.opportunity_id.stage_id',
        readonly=False,
    )

    @api.depends('move_lines.state', 'move_lines.date', 'move_type')
    def _compute_scheduled_date(self):
        super()._compute_scheduled_date()
        for picking in self:
            picking.sale_id.write({'pick_scheduled_date': picking.scheduled_date})

    def _set_scheduled_date(self):
        super()._set_scheduled_date()
        for picking in self:
            picking.sale_id.write({'pick_scheduled_date': picking.scheduled_date})
