# Copyright 2024 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    default_department_id = fields.Many2one(comodel_name="hr.department", string="Default Department")
