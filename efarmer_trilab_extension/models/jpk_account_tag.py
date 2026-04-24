# Copyright 2025 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import fields, models


class JpkAccountTag(models.Model):
    _inherit = 'jpk.account.tag'

    jpk_apply_to = fields.Selection(
        selection=[
            ('0', 'All'),
            ('-1', 'Negative'),
            ('1', 'Positive'),
        ],
        default='0',
        required=True,
    )
