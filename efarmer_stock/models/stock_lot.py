# -*- coding: utf-8 -*-
# Copyright 2026 VentorTech OU
# Part of Ventor modules. See LICENSE file for full copyright and licensing details.
from odoo import _, fields, models, api
from odoo.exceptions import AccessError

EDITOR_GROUP = 'efarmer_stock.group_serial_metadata_editor'


class StockLot(models.Model):
    _inherit = "stock.lot"

    is_assigned = fields.Boolean(
        string="Assigned", help="Technical field to mark assigned serial numbers"
    )
    additional_sn_ids = fields.Many2many(
        'stock.lot.additional.sn', string='Additional S/N', copy=False, tracking=True)
    firmware_ids = fields.Many2many(
        'stock.lot.firmware', string='Firmware', copy=False, tracking=True)
    can_edit_metadata = fields.Boolean(compute='_compute_can_edit_metadata')

    def _compute_can_edit_metadata(self):
        for lot in self:
            lot.can_edit_metadata = self.env.user.has_group(EDITOR_GROUP)

    def _check_metadata_rights(self):
        if self.env.su or self.env.user.has_group('base.group_system'):
            return
        if not self.env.user.has_group(EDITOR_GROUP):
            raise AccessError("You are not allowed to change Additional S/N or Firmware.")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'additional_sn_ids' in vals or 'firmware_ids' in vals:
                self._check_metadata_rights()
        return super().create(vals_list)

    def write(self, vals):
        if 'additional_sn_ids' in vals or 'firmware_ids' in vals:
            self._check_metadata_rights()
        return super().write(vals)
