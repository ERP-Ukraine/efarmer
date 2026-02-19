# Copyright 2021 VentorTech OU
# See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    print_labels_format = fields.Selection(
        readonly=False,
        related='company_id.print_labels_format',
    )

    print_product_zld_label_id = fields.Many2one(
        readonly=False,
        related='company_id.print_product_zld_label_id',
    )
