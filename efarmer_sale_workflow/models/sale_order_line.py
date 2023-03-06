# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).


from odoo import models, _


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def open_replacement_wizard(self):
        new_wizard = self.env['product.variant.replacement.wizard'].create(
            {
                'product_tmpl_id': self.product_template_id.id,
                'sale_line_id': self.id,
            }
        )
        view_id = self.env.ref('efarmer_sale_workflow.product_variant_replacement_wizard_view_form').id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Select Product Replacement'),
            'res_model': 'product.variant.replacement.wizard',
            'view_mode': 'form',
            'res_id': new_wizard.id,
            'view_id': view_id,
            'target': 'new',
            'context': self.env.context,
        }
