# See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    integration_id = fields.Many2one(
        string='E-Commerce Store',
        comodel_name='sale.integration',
        copy=False,
    )

    integration_transaction_id = fields.Many2one(
        comodel_name='external.order.transaction',
        string='External Transaction',
        domain="[('integration_id', '=', integration_id)]",
        copy=False,
    )
