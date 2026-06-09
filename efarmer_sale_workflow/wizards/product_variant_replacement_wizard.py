# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).


from odoo import models, fields, _
from odoo.exceptions import ValidationError


class OrderLineProductReplacementWizard(models.TransientModel):
    _name = "order.line.product.replacement.wizard"
    _description = "Product Replacement Wizard"

    product_tmpl_id = fields.Many2one(
        comodel_name="product.template",
        string="Current Product",
        readonly=True,
    )

    sale_line_id = fields.Many2one(
        comodel_name="sale.order.line",
        string="Sale Order Line",
        readonly=True,
    )

    product_uom_qty = fields.Float(related="sale_line_id.product_uom_qty")

    replacement_line_ids = fields.One2many(
        comodel_name="product.replacement.lines",
        string="Replacement Lines",
        inverse_name="replacement_id",
        required=True,
    )

    def apply_replacement(self):
        if (
            sum(self.replacement_line_ids.mapped("product_uom_qty"))
            != self.product_uom_qty
        ):
            raise ValidationError(
                _(
                    "You cannot apply new variants if before and after quantities are not equal. "
                    "To continue set the same quantities at the top Quantity and Replacements Tab."
                )
            )

        if len(self.replacement_line_ids) >= 1:
            self.sale_line_id.product_id = self.replacement_line_ids[0].product_id.id
            self.sale_line_id.name = self.replacement_line_ids[
                0
            ].product_id.get_product_multiline_description_sale()
            self.sale_line_id.product_uom_qty = self.replacement_line_ids[
                0
            ].product_uom_qty

            # enter in for loop only if replacement_line_ids > 1
            for line in self.replacement_line_ids[1:]:
                default = {
                    "order_id": self.sale_line_id.order_id.id,
                    "product_id": line.product_id.id,
                    "name": line.product_id.get_product_multiline_description_sale(),
                    "product_uom_qty": line.product_uom_qty,
                }
                self.sale_line_id.copy(default=default)


class ProductReplacements(models.TransientModel):
    _name = "product.replacement.lines"
    _description = "Product Replacement Line"

    replacement_id = fields.Many2one(
        comodel_name="order.line.product.replacement.wizard",
        string="Replacement",
        ondelete="cascade",
    )

    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Replacement Product",
    )

    product_uom_qty = fields.Float(
        string="Quantity",
        default=0.0,
        digits="Product Unit",
        required=True,
    )
