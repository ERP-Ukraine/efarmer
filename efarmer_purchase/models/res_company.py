# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import fields, models, _


class ResCompany(models.Model):
    _inherit = 'res.company'

    fin_manager_id = fields.Many2one(
        comodel_name='res.users',
        string='Financial Manager',
    )

