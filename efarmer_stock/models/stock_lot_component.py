# Copyright 2026 VentorTech OU
# Part of Ventor modules. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class StockLotAdditionalSn(models.Model):
    _name = 'stock.lot.additional.sn'
    _description = 'Lot Additional S/N'
    _order = 'name'

    name = fields.Char(string='Additional S/N', required=True)

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'This Additional S/N already exists.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name'):
                vals['name'] = vals['name'].strip()
        return super().create(vals_list)


class StockLotFirmware(models.Model):
    _name = 'stock.lot.firmware'
    _description = 'Lot Firmware'
    _order = 'name'

    name = fields.Char(string='Firmware', required=True)

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'This Firmware already exists.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name'):
                vals['name'] = vals['name'].strip()
        return super().create(vals_list)
