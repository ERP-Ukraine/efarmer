from odoo import fields, models


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

    def action_done(self):
        res = super().action_done()
        # THERE IS COSTYL' (FIXME)
        # In case of backorder creation (at least)
        # the original picking isn't recompute his state.
        self._compute_state()
        return res
