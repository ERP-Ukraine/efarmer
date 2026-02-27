# Copyright 2026 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from datetime import datetime

from odoo import fields, models


class HrVersion(models.Model):
    _inherit = "hr.version"

    employee_type = fields.Selection(
        selection_add=[("outstaff", "Outstaff")], ondelete={"outstaff": "set default"}
    )
