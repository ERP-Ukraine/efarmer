# Copyright 2026 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).


from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    youtrack_id = fields.Char(
        string="YouTrack ID",
        groups="hr.group_hr_user",
    )
