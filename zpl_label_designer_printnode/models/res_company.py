# Copyright 2021 VentorTech OU
# See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class Company(models.Model):
    _inherit = 'res.company'

    print_labels_format = fields.Selection(
        selection_add=[('zld_label', 'Label From ZPL Designer')],
    )

    print_product_zld_label_id = fields.Many2one(
        comodel_name='zld.label',
        string='Default Product Label from ZPL Designer',
        domain=lambda self: self._get_zld_label_domain(),
    )

    def _get_zld_label_domain(self):
        return [
            ('is_published', '=', True),
            ('model_id', '=', 'product.product')
        ]
