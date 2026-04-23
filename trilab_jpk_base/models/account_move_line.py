from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    x_pl_vat_gtu = fields.Many2one(comodel_name='jpk.gtu', string='JPK GTU')

    @api.onchange('product_id')
    def onchange_product_id(self):
        if self.product_id:
            self.x_pl_vat_gtu = self.product_id.x_pl_vat_gtu

    @api.model_create_multi
    def create(self, vals_list):
        # update GTU on lines
        for vals in vals_list:
            if (
                not vals.get('x_pl_vat_gtu')
                and vals.get('display_type') in {'cogs', 'product'}
                and self.move_id.browse(vals.get('move_id')).is_sale_document()
                and (product_id := self.product_id.browse(vals.get('product_id')))
            ):
                vals['x_pl_vat_gtu'] = product_id.x_pl_vat_gtu.id

        return super().create(vals_list)
