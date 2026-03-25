# See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class IntegrationLogType(models.Model):
    _name = 'integration.log.type'
    _description = 'Integration Log Type'

    code = fields.Char(
        string='Code',
        required=True,
    )

    name = fields.Char(
        string='Name',
        required=True,
    )
