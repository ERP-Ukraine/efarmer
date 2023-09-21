from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo import fields, models, api


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    paid_on_date = fields.Date(
        string='Paid on',
    )

    opportunity_stage_id = fields.Many2one(
        comodel_name='crm.stage',
        string='Opportunity Stage',
        related='opportunity_id.stage_id',
        readonly=False,
    )

    state = fields.Selection(
        selection_add=[
            ('to_payment', 'To Payment'),
            ('to_confirm', 'To Confirm'),
            ('sale',)
        ],
    )

    priority = fields.Selection([
            ('0', 'Low priority'),
            ('1', 'Medium priority'),
            ('2', 'High priority'),
            ('3', 'Urgent'),
        ],
        string='Priority',
        default='0',
    )

    pick_scheduled_date = fields.Date(
        string='Scheduled Delivery Date',
        tracking=True,
        compute='_compute_pick_scheduled_date',
        store=True,
        help='Scheduled date of last modified stock picking',
    )

    def action_to_confirm(self):
        return self.write({'state': 'to_confirm'})

    def action_to_payment(self):
        return self.write({'state': 'to_payment'})

    @api.depends('picking_ids', 'picking_ids.scheduled_date', 'state', 'delivery_state')
    def _compute_pick_scheduled_date(self):
        for order in self:
            if order.state != 'sale' or order.delivery_state == 'done':
                order.pick_scheduled_date = None
            else:
                active_picks = order.picking_ids.filtered(
                    lambda p: p.state not in ['done', 'cancel'])
                order.pick_scheduled_date = active_picks[0].scheduled_date if active_picks else None

    def _get_default_delivery_term_id(self):
        return self.env['delivery.terms'].search([('default_for_company', '=', True), ('company_id', '=', self.env.company.id)], limit=1)

    delivery_term_id = fields.Many2one('delivery.terms', string='Delivery Terms', domain="[('company_id', '=', company_id)]", default=_get_default_delivery_term_id,)
    commitment_date = fields.Datetime(default=lambda self: datetime.today() + relativedelta(days=self._get_default_delivery_term_id().delivery_days))
    tag_ids = fields.Many2many(default=lambda self: self.delivery_term_id.tag_ids)

    @api.onchange('delivery_term_id')
    def _onchange_action(self):
        for order in self:
            if not order.commitment_date:
                order.commitment_date = (
                    datetime.today() + relativedelta(days=order.delivery_term_id.delivery_days)
                )
            if not order.tag_ids:
                order.tag_ids = order.delivery_term_id.tag_ids
