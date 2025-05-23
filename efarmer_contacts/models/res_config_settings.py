# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    enable_fisc_pos_auto_calc = fields.Boolean(
        related='company_id.enable_fisc_pos_auto_calc',
        readonly=False,
    )
