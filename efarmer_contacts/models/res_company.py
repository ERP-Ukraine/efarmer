# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    enable_fisc_pos_auto_calc = fields.Boolean(
        string='Enable auto-calculation of Fiscal Position for Contacts',
        default=False,
    )
