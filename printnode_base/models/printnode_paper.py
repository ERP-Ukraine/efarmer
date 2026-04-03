# Copyright 2021 VentorTech OU
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class PrintNodePaper(models.Model):
    """ Direct Print Paper entity
    """
    _name = 'printnode.paper'
    _description = 'Direct Print Paper'

    name = fields.Char(
        'Name',
        size=64,
        required=True
    )

    width = fields.Integer('Width')

    height = fields.Integer('Height')
