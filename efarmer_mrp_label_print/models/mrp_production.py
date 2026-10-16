# -*- coding: utf-8 -*-
from odoo import models


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    def action_open_label_print_wizard(self):
        wizard = self.env["mrp.label.print.wizard"].create(
            {
                "production_ids": [(6, 0, self.ids)],
                "line_ids": [
                    (0, 0, vals) for vals in self._get_label_print_line_vals()
                ],
            }
        )
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Print Labels"),
            "res_model": "mrp.label.print.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    def _get_label_print_line_vals(self):
        """Collect components (by consumed quants) and finished product of the MOs.

        Move lines are grouped by quant key: product, lot, location, package, owner.
        """
        Line = self.env["mrp.label.print.wizard.line"]
        vals_list = []
        for production in self:
            grouped = {}
            raw_moves = production.move_raw_ids.filtered(lambda m: m.state != "cancel")
            for move_line in raw_moves.move_line_ids:
                key = (
                    "component",
                    move_line.product_id,
                    move_line.lot_id,
                    move_line.location_id,
                    move_line.package_id,
                    move_line.owner_id,
                )
                grouped[key] = grouped.get(key, 0.0) + move_line.quantity_product_uom

            finished_moves = production.move_finished_ids.filtered(
                lambda m: m.state != "cancel" and m.product_id == production.product_id
            )
            if finished_moves.move_line_ids:
                for move_line in finished_moves.move_line_ids:
                    key = (
                        "finished",
                        move_line.product_id,
                        move_line.lot_id,
                        move_line.location_dest_id,
                        move_line.result_package_id,
                        move_line.owner_id,
                    )
                    grouped[key] = (
                        grouped.get(key, 0.0) + move_line.quantity_product_uom
                    )
            else:
                # MO is not produced yet: take the producing lot and quantity from the MO itself
                qty = production.qty_producing or production.product_qty
                key = (
                    "finished",
                    production.product_id,
                    production.lot_producing_id,
                    production.location_dest_id,
                    self.env["stock.quant.package"],
                    self.env["res.partner"],
                )
                grouped[key] = production.product_uom_id._compute_quantity(
                    qty, production.product_id.uom_id
                )

            for (
                line_type,
                product,
                lot,
                location,
                package,
                owner,
            ), qty in grouped.items():
                if qty <= 0:
                    continue
                quant = self.env["stock.quant"].search(
                    [
                        ("product_id", "=", product.id),
                        ("lot_id", "=", lot.id),
                        ("location_id", "=", location.id),
                        ("package_id", "=", package.id),
                        ("owner_id", "=", owner.id),
                    ],
                    limit=1,
                )
                vals_list.append(
                    {
                        "production_id": production.id,
                        "line_type": line_type,
                        "product_id": product.id,
                        "lot_id": lot.id,
                        "location_id": location.id,
                        "quant_id": quant.id,
                        "quantity": qty,
                        "label_qty": Line._get_default_label_qty(product, qty),
                    }
                )
        return vals_list
