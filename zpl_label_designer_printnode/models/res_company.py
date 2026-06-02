# Copyright 2021 VentorTech OU
# See LICENSE file for full copyright and licensing details.

from odoo import fields, models


WIZARD_LABEL_FORMAT_SELECTION = [
    ('dymo', 'Dymo'),
    ('2x7xprice', '2 x 7 with price'),
    ('4x7xprice', '4 x 7 with price'),
    ('4x12', '4 x 12'),
    ('4x12xprice', '4 x 12 with price'),
    ('zpl', 'ZPL Labels'),
    ('zplxprice', 'ZPL Labels with price'),
    ('zld_label', 'Label From ZPL Designer'),
]


class Company(models.Model):
    _inherit = 'res.company'

    print_labels_format = fields.Selection(
        selection_add=[('zld_label', 'Label From ZPL Designer')],
    )

    print_wizard_label_format = fields.Selection(
        WIZARD_LABEL_FORMAT_SELECTION,
        string="Default Product Label Format for Print Label Wizards",
        help='Set the default label printing format for Print Labels wizards',
    )

    print_product_zld_label_id = fields.Many2one(
        comodel_name='zld.label',
        string='Default Scenario Product Label from ZPL Designer',
        domain=lambda self: self._get_zld_label_domain(),
    )

    print_pt_zld_label_id = fields.Many2one(
        comodel_name='zld.label',
        string='Default Product Template Label from ZPL Designer',
        domain=lambda self: self._get_pt_zld_label_domain(),
    )

    print_pp_zpl_label_id = fields.Many2one(
        comodel_name='zld.label',
        string='Default Product Variant Label from ZPL Designer',
        domain=lambda self: self._get_zld_label_domain(),
    )

    print_picking_zld_label_id = fields.Many2one(
        comodel_name='zld.label',
        string='Default Picking Product Label from ZPL Designer',
        domain=lambda self: self._get_zld_label_domain(),
    )

    print_batch_zld_label_id = fields.Many2one(
        comodel_name='zld.label',
        string='Default Batch Picking Product Label from ZPL Designer',
        domain=lambda self: self._get_zld_label_domain(),
    )

    print_mrp_zld_label_id = fields.Many2one(
        comodel_name='zld.label',
        string='Default Manufacturing Product Label from ZPL Designer',
        domain=lambda self: self._get_zld_label_domain(),
    )

    def _get_zld_label_domain(self):
        return [
            ('is_published', '=', True),
            ('model_id', '=', 'product.product')
        ]

    def _get_pt_zld_label_domain(self):
        return [
            ('is_published', '=', True),
            ('model_id', '=', 'product.template')
        ]
