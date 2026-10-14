# Copyright 2026 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import _, api, models
from odoo.exceptions import UserError
from odoo.tools import float_is_zero


class StockValuationLayerRevaluation(models.TransientModel):
    _inherit = "stock.valuation.layer.revaluation"

    # This is OVERRIDE method for
    # remove UserError(_("You cannot revalue a product with an empty or negative stock."))
    # Task EF-270, EF-493
    @api.model
    def default_get(self, default_fields):
        res = super(models.TransientModel, self).default_get(default_fields)
        context = self.env.context
        if res.get("lot_id"):
            lot = self.env["stock.lot"].browse(res["lot_id"]).exists()
            if lot:
                res["product_id"] = lot.product_id.id
        if context.get("active_model") == "stock.valuation.layer":
            # coming from action button "Adjust Valuation" in valuation layer list view
            active_ids = context.get("active_ids")
            layers = self.env["stock.valuation.layer"].browse(active_ids).exists()
            product = layers.product_id
            if len(product) > 1:
                raise UserError(_("You cannot revalue multiple products at once"))
            if any(
                float_is_zero(layer.remaining_qty, precision_rounding=product.uom_id.rounding)
                for layer in layers
            ):
                raise UserError(_("You cannot adjust the valuation of a layer with zero quantity"))
            res["adjusted_layer_ids"] = active_ids
            res["product_id"] = product.id
        product = self.env["product.product"].browse(res.get("product_id"))
        if "product_id" in default_fields:
            if not product:
                raise UserError(_("You cannot adjust valuation without a product"))
            if product.categ_id.property_cost_method == "standard":
                raise UserError(_("You cannot revalue a product with a standard cost method."))
            # Removed on purpose:
            # if product.quantity_svl <= 0:
            #     raise UserError(_("You cannot revalue a product with an empty or negative stock."))
            if (
                "account_journal_id" not in res
                and "account_journal_id" in default_fields
                and product.categ_id.property_valuation == "real_time"
            ):
                accounts = product.product_tmpl_id.get_product_accounts()
                res["account_journal_id"] = accounts["stock_journal"].id
        return res
