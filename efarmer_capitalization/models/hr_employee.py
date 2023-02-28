# Copyright 2023 VentorTech OU
# Part of Ventor modules. See LICENSE file for full copyright and licensing details.
from odoo import models, fields, _


class HrEmployeePrivate(models.Model):
    _inherit = "hr.employee"

    account_asset_counterpart_id = fields.Many2one(
        'account.account',
        string='Account Asset Counterpart',
        check_company=True,
        help="Account used as counterpart for entries related to this asset.",
        tracking=True,
    )


