# -*- coding: utf-8 -*-
# Copyright 2026 VentorTech OU
# Part of Ventor modules. See LICENSE file for full copyright and licensing details.
from odoo import api, models


class StockQuant(models.Model):
    _inherit = "stock.quant"

    @api.model
    def create(self, vals):
        res = super(StockQuant, self).create(vals)
        for record in res:
            if (
                record.product_id.tracking == "serial"
                and record.lot_id
                and not record.lot_id.is_assigned
            ):
                record.lot_id.is_assigned = True
        return res

    def write(self, vals):
        res = super().write(vals)
        for record in self:
            if (
                record.product_id.tracking == "serial"
                and record.lot_id
                and not record.lot_id.is_assigned
            ):
                record.lot_id.is_assigned = True
        return res
