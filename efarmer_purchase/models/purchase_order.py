# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import fields, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    state = fields.Selection(
        selection_add=[
            ('confirm_demand', 'Confirm Demand'),
            ('fin_approve', 'Financial Approval'),
            ('purchase',)
        ],
    )

    def action_confirm_rfq(self):
        return self.write({'state': 'confirm_demand'})

    def action_confirm_demand(self):
        return self.write({'state': 'fin_approve'})

    def button_confirm(self):
        """
        Override standart method to have possibility to confirm PO
        also in 'Financial Approval' state
        """
        for order in self:
            if order.state not in ['draft', 'sent', 'fin_approve']:
                continue
            order._add_supplier_to_product()
            # Deal with double validation process
            if order._approval_allowed():
                order.button_approve()
            else:
                order.write({'state': 'to approve'})
            if order.partner_id not in order.message_partner_ids:
                order.message_subscribe([order.partner_id.id])
        return True
