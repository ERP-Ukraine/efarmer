# -*- coding: utf-8 -*-
# Copyright 2026 VentorTech OU
# Part of Ventor modules. See LICENSE file for full copyright and licensing details.
from odoo import models


class ReturnPicking(models.TransientModel):
    _inherit = 'stock.return.picking'

    def _prepare_picking_default_values_based_on(self, picking):
        res = super()._prepare_picking_default_values_based_on(picking)
        res["origin"] = f"Return of {picking.name}"
        return res
