from odoo import api, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def has_kit_product(self):
        """Checks if current line has Kit Product"""
        if not len(self) == 1 or not self.product_id:
            return False
        boms = self.env["mrp.bom"]._bom_find(
            self.product_id, company_id=self.company_id.id, bom_type="phantom"
        )
        return bool(boms)

    @api.depends('product_id', 'company_id', 'currency_id', 'product_uom')
    def _compute_purchase_price(self):
        for line in self.filtered(lambda x: x.has_kit_product()):
            line.product_id.button_bom_cost()
        super()._compute_purchase_price()

    def copy(self, default=None):
        default = dict(default or {})
        rec = super().copy(default)
        if rec.has_kit_product():
            rec._compute_purchase_price()
        return rec


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _action_confirm(self):
        res = super()._action_confirm()

        # Explicitly recompute sale.order.line:purchase_price
        self.mapped("order_line")._compute_purchase_price()

        return res
