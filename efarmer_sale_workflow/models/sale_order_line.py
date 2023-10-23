# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).


from odoo import models, fields, _


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    detailed_type = fields.Selection(
        related='product_id.detailed_type',
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
