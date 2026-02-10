from odoo import _, api, fields, models


class ProductProduct(models.Model):
    _name = "product.product"
    _inherit = "product.product"
    _description = "Product"

    # Override
    def button_bom_cost(self):
        """Update Kit's cost from BoM without creating account moves."""
        for product in self:
            bom = self.env["mrp.bom"]._bom_find(product=product)
            boms_to_recompute = list(self._get_all_kit_boms(bom))
            product.standard_price = product._get_price_from_bom(
                boms_to_recompute=boms_to_recompute
            )

    def _get_all_kit_boms(self, bom):
        """Returns kit bom including it's children kits"""
        if bom and bom.type == "phantom":
            yield bom
        for line in bom.bom_line_ids:
            yield from self._get_all_kit_boms(line.child_bom_id)
