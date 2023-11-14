# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import fields, models, api


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    product_vat_id = fields.Many2one(
        comodel_name='product.vat',
        string='Product Vat',
    )

    is_auto_calc_taxes = fields.Boolean(
        default=False,
        string='Auto-calculate taxes'
    )

    @api.onchange('order_line')
    def _onchange_line_tax_id(self):
        if self.is_auto_calc_taxes:
            self.order_line._compute_tax_id()

    def action_view_helpdesk_tickets(self):
        action = self.env['ir.actions.act_window']._for_xml_id('helpdesk.helpdesk_ticket_action_main_tree')
        helpdesk_ticket_ids = self.env['helpdesk.ticket'].search([('sale_order_id', 'in', self.ids)])
        action['res_ids'] = helpdesk_ticket_ids.ids
        return action
