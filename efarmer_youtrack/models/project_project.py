# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).


from odoo import fields, models


class Project(models.Model):
    _inherit = "project.project"

    project_code = fields.Char(
        string="Project Code",
    )

    youtrack_id = fields.Char(
        string="YouTrack ID",
    )
