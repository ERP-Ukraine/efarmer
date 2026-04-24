# See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class AccountTax(models.Model):
    _name = 'account.tax'
    _inherit = ['account.tax', 'integration.model.mixin']

    integration_id = fields.Many2one(
        comodel_name='sale.integration',
        string='E-Commerce Store',
    )
