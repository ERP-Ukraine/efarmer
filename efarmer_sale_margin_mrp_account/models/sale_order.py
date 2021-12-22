from odoo import api, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def has_kit_product(self):
        """Checks if current line has Kit Product"""
        if not len(self) == 1 or not self.product_id:
            return False
        boms = self.env['mrp.bom']._bom_find(product=self.product_id,
                                             company_id=self.company_id.id,
                                             bom_type='phantom')
        return bool(boms)

    def _compute_margin(self, order_id, product_id, product_uom_id):
        # recompute product cost from BoM when computing margin
        if self.has_kit_product():
            self.product_id.button_bom_cost()
        return super()._compute_margin(order_id, product_id, product_uom_id)

    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        rec = super().copy(default)
        if rec.has_kit_product():
            rec._recompute_margin()
        return rec


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _action_confirm(self):
        res = super()._action_confirm()
        for order_line in self.mapped('order_line'):
            order_line.purchase_price = order_line._compute_margin(
                order_line.order_id,
                order_line.product_id,
                order_line.product_uom)
        return res
