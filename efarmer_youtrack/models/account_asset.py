# Copyright 2026 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).


from odoo import models, fields


class AccountAsset(models.Model):
    _inherit = "account.asset"

    youtrack_id = fields.Char(
        string="YouTrack ID",
    )
