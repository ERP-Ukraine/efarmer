from odoo import api, models


class ProductLabelLayout(models.TransientModel):
    _inherit = 'product.label.layout'

    @api.depends('print_format', 'zld_label_id')
    def _compute_printer_id(self):
        """
        Overrides _compute_printer_id to add dependency on 'zld_label_id'.
        """
        return super()._compute_printer_id()
