from odoo import models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _init_product_label_layout_wizard(
        self, active_model, move_quantity, product_ids, product_line_ids, print_format, **kwargs
    ):
        """
        Overriden to pass zld_label_id field to wizard.
        """
        if print_format == 'zld_label' and 'zld_label_id' not in kwargs:
            kwargs['zld_label_id'] = self.env.company.print_product_zld_label_id.id

        return super()._init_product_label_layout_wizard(
            active_model, move_quantity, product_ids, product_line_ids, print_format,
            **kwargs
        )
