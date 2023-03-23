# Copyright 2023 VentorTech OU
# Part of Ventor modules. See LICENSE file for full copyright and licensing details.
from odoo import models, fields, _


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    related_contact_id = fields.Many2one(
        'res.partner',
        string='Related Contact',
    )
