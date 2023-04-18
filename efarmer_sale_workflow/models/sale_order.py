from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

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

    def action_to_confirm(self):
        return self.write({'state': 'to_confirm'})

    def action_to_payment(self):
        return self.write({'state': 'to_payment'})
