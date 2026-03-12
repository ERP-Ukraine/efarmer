# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).


from odoo import models, fields, _


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    product_type = fields.Selection(related='product_id.type')
    qty_to_deliver = fields.Float(store=True)
    planned_shipping_date = fields.Date(
        string='Planned Shipping Date',
        related="order_id.planned_shipping_date",
        store=True,
    )
    efarmer_confirm_date = fields.Date(
        string='Confirm Date',
        related="order_id.efarmer_confirm_date",
        store=True,
    )
    efarmer_client_type = fields.Many2one(
        string='Client Type',
        related='order_partner_id.efarmer_client_type',
        store=True,
    )
    paid_on_date = fields.Date(
        string='Paid on',
        related="order_id.paid_on_date",
        store=True,
    )

    def open_replacement_wizard(self):
        new_wizard = self.env['order.line.product.replacement.wizard'].create(
            {
                'product_tmpl_id': self.product_template_id.id,
                'sale_line_id': self.id,
            }
        )
        action = self.env['ir.actions.act_window']._for_xml_id(
            'efarmer_sale_workflow.launch_order_line_product_replacement_wizard')
        action['res_id'] = new_wizard.id
        action['name'] = _('Select Product Replacement')
        return action
