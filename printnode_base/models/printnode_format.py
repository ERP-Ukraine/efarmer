# Copyright 2021 VentorTech OU
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class PrintNodeFormat(models.Model):
    """ Direct Print Content Type
    """
    _name = 'printnode.format'
    _description = 'Direct Print Format'

    name = fields.Char(
        'Content Type',
        size=8,
        required=True
    )

    qweb = fields.Char(
        'QWeb Name',
        size=16,
        required=True
    )
