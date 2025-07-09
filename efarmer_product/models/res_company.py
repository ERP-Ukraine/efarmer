# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    enable_so_tax_auto_calc = fields.Boolean(
        string='Enable Auto-calculate taxes on Sales Orders',
        default=False,
    )
