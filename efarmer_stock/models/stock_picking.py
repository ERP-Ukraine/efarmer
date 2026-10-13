# -*- coding: utf-8 -*-
# Copyright 2026 VentorTech OU
# Part of Ventor modules. See LICENSE file for full copyright and licensing details.
from odoo import _, models
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def write(self, vals):
        pickings_to_check = self.env["stock.picking"]
        if vals.get("location_id") or vals.get("location_dest_id"):
            active_pickings = self.filtered(
                lambda p: p.state not in ("draft", "done", "cancel")
            )
            source_changed_pickings = active_pickings.filtered(
                lambda p: vals.get("location_id")
                and p.location_id.id != vals["location_id"]
            )
            dest_changed_pickings = active_pickings.filtered(
                lambda p: vals.get("location_dest_id")
                and p.location_dest_id.id != vals["location_dest_id"]
            )
            pickings_to_check = source_changed_pickings | dest_changed_pickings
            # Changing the source location unlinks the reserved move lines and
            # clears move_orig_ids, which breaks multi-step chains.
            chained_pickings = source_changed_pickings.filtered(
                lambda p: p.move_ids.move_orig_ids
            )
            if chained_pickings:
                raise UserError(
                    _(
                        "Source location cannot be changed for chained transfers: %s",
                        ", ".join(chained_pickings.mapped("name")),
                    )
                )
        res = super().write(vals)
        pickings_to_check._check_available_locations()
        return res

    def action_confirm(self):
        self._check_available_locations()
        return super().action_confirm()

    def _check_available_locations(self):
        available_locations = self.env.user.available_location_ids
        if not available_locations:
            return
        forbidden_locations = []
        for picking in self.filtered(lambda p: p.picking_type_code == "internal"):
            for location in picking.location_id | picking.location_dest_id:
                if not any(location._child_of(loc) for loc in available_locations):
                    forbidden_locations.append(
                        f"{picking.name}: {location.display_name}"
                    )
        if forbidden_locations:
            raise UserError(
                _(
                    "You are not allowed to use these locations in internal transfers:\n%s",
                    "\n".join(forbidden_locations),
                )
            )
