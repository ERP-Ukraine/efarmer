# -*- coding: utf-8 -*-
# Copyright 2026 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import models
from odoo.tools import float_is_zero
from collections import defaultdict
from datetime import datetime


class ProductProduct(models.Model):
    _inherit = "product.product"

    def _run_fifo_vacuum(self, company=None):
        if company is None:
            company = self.env.company
        ValuationLayer = self.env["stock.valuation.layer"].sudo()
        svls_to_vacuum_by_product = defaultdict(lambda: ValuationLayer)
        res = ValuationLayer.read_group(
            [
                ("product_id", "in", self.ids),
                ("remaining_qty", "<", 0),
                ("stock_move_id", "!=", False),
                ("company_id", "=", company.id),
            ],
            ["ids:array_agg(id)", "create_date:min"],
            ["product_id"],
            orderby="create_date, id",
        )
        min_create_date = datetime.max
        for group in res:
            svls_to_vacuum_by_product[group["product_id"][0]] = ValuationLayer.browse(
                group["ids"]
            )
            min_create_date = min(min_create_date, group["create_date"])
        all_candidates_by_product = defaultdict(lambda: ValuationLayer)
        res = ValuationLayer.read_group(
            [
                ("product_id", "in", self.ids),
                ("remaining_qty", ">", 0),
                ("company_id", "=", company.id),
                ("create_date", ">=", min_create_date),
            ],
            ["ids:array_agg(id)"],
            ["product_id"],
            orderby="id",
        )
        for group in res:
            all_candidates_by_product[group["product_id"][0]] = ValuationLayer.browse(
                group["ids"]
            )

        new_svl_vals_real_time = []
        new_svl_vals_manual = []
        real_time_svls_to_vacuum = ValuationLayer

        for product in self:
            all_candidates = all_candidates_by_product[product.id]
            current_real_time_svls = ValuationLayer
            for svl_to_vacuum in svls_to_vacuum_by_product[product.id]:
                # We don't use search to avoid executing _flush_search and to decrease interaction with DB
                candidates = all_candidates.filtered(
                    lambda r: r.create_date > svl_to_vacuum.create_date
                    or r.create_date == svl_to_vacuum.create_date
                    and r.id > svl_to_vacuum.id
                )
                if not candidates:
                    break
                qty_to_take_on_candidates = abs(svl_to_vacuum.remaining_qty)
                qty_taken_on_candidates = 0
                tmp_value = 0
                for candidate in candidates:
                    qty_taken_on_candidate = min(
                        candidate.remaining_qty, qty_to_take_on_candidates
                    )
                    qty_taken_on_candidates += qty_taken_on_candidate

                    candidate_unit_cost = (
                        candidate.remaining_value / candidate.remaining_qty
                    )
                    value_taken_on_candidate = (
                        qty_taken_on_candidate * candidate_unit_cost
                    )
                    value_taken_on_candidate = candidate.currency_id.round(
                        value_taken_on_candidate
                    )
                    new_remaining_value = (
                        candidate.remaining_value - value_taken_on_candidate
                    )

                    candidate_vals = {
                        "remaining_qty": candidate.remaining_qty
                        - qty_taken_on_candidate,
                        "remaining_value": new_remaining_value,
                    }
                    candidate.write(candidate_vals)
                    if not (candidate.remaining_qty > 0):
                        all_candidates -= candidate

                    qty_to_take_on_candidates -= qty_taken_on_candidate
                    tmp_value += value_taken_on_candidate
                    if float_is_zero(
                        qty_to_take_on_candidates,
                        precision_rounding=product.uom_id.rounding,
                    ):
                        break

                # Get the estimated value we will correct.
                remaining_value_before_vacuum = (
                    svl_to_vacuum.unit_cost * qty_taken_on_candidates
                )
                new_remaining_qty = (
                    svl_to_vacuum.remaining_qty + qty_taken_on_candidates
                )
                corrected_value = remaining_value_before_vacuum - tmp_value
                svl_to_vacuum.write(
                    {
                        "remaining_qty": new_remaining_qty,
                    }
                )

                # Don't create a layer or an accounting entry if the corrected value is zero.
                if svl_to_vacuum.currency_id.is_zero(corrected_value):
                    continue

                corrected_value = svl_to_vacuum.currency_id.round(corrected_value)

                move = svl_to_vacuum.stock_move_id
                new_svl_vals = (
                    new_svl_vals_real_time
                    if product.valuation == "real_time"
                    else new_svl_vals_manual
                )
                new_svl_vals.append(
                    {
                        "product_id": product.id,
                        "value": corrected_value,
                        "unit_cost": 0,
                        "quantity": 0,
                        "remaining_qty": 0,
                        "stock_move_id": move.id,
                        "company_id": move.company_id.id,
                        "description": "Revaluation of %s (negative inventory)"
                        % (move.picking_id.name or move.name),
                        "stock_valuation_layer_id": svl_to_vacuum.id,
                    }
                )
                if product.valuation == "real_time":
                    current_real_time_svls |= svl_to_vacuum
            real_time_svls_to_vacuum |= current_real_time_svls
        ValuationLayer.create(new_svl_vals_manual)
        vacuum_svls = ValuationLayer.create(new_svl_vals_real_time)

        # If some negative stock were fixed, we need to recompute the standard price.
        product_ids_in_res = {item["product_id"][0] for item in res}
        for product in self:
            if product.id in product_ids_in_res:
                product = product.with_company(company.id)
                if product.cost_method == "average" and not float_is_zero(
                    product.quantity_svl, precision_rounding=product.uom_id.rounding
                ):
                    product.sudo().with_context(disable_auto_svl=True).write(
                        {"standard_price": product.value_svl / product.quantity_svl}
                    )

        vacuum_svls._validate_accounting_entries()
        self._create_fifo_vacuum_anglo_saxon_expense_entries(
            zip(vacuum_svls, real_time_svls_to_vacuum)
        )
