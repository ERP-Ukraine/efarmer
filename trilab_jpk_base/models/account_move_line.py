from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    x_pl_vat_gtu = fields.Many2one('jpk.gtu', 'JPK GTU', export_string_translation=False)

    @api.onchange('product_id')
    def onchange_product_id(self):
        if self.product_id:
            self.x_pl_vat_gtu = self.product_id.x_pl_vat_gtu

    @api.model_create_multi
    def create(self, vals_list):
        line_ids = super().create(vals_list)

        # update GTU on lines - after creation, to have display_type populated
        for line_id in line_ids.filtered(
            lambda l_id: not l_id.x_pl_vat_gtu and l_id.display_type in {'cogs', 'product'} and l_id.product_id
        ):
            if line_id.move_id.is_sale_document():
                line_id.x_pl_vat_gtu = line_id.product_id.x_pl_vat_gtu

        return line_ids
