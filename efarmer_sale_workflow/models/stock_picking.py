from odoo import fields, models, api


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    sale_state = fields.Selection(
        related='sale_id.state',
        string='Sale Status',
        readonly=False,
    )
    # product_vat_id = fields.Many2one(
    #     related='sale_id.product_vat_id', # TODO module efarmer_product must be migrated
    #     string='VAT ID',
    # )
    opportunity_stage_id = fields.Many2one(
        comodel_name='crm.stage',
        string='Opportunity Stage',
        related='sale_id.opportunity_id.stage_id',
        readonly=False,
    )
    sale_priority = fields.Selection(
        related='sale_id.priority',
        string='Sale Priority',
    )

    def button_validate(self):
        res = super(StockPicking, self).button_validate()
        if res is True:
            for pick in self:
                active_picks = pick.sale_id.picking_ids.filtered(
                    lambda p: p.state not in ('done', 'cancel')
                )
                if not active_picks:
                    pick.sale_id.write({'priority': '0'})
        return res

    def action_cancel(self):
        res = super(StockPicking, self).action_cancel()
        if res is True:
            for pick in self:
                active_picks = pick.sale_id.picking_ids.filtered(
                    lambda p: p.state not in ('done', 'cancel')
                )
                if not active_picks:
                    pick.sale_id.write({'priority': '0'})
        return res
