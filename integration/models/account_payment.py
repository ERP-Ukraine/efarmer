# See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    integration_id = fields.Many2one(
        comodel_name='sale.integration',
        string='E-Commerce Store',
        copy=False,
    )

    integration_transaction_id = fields.Many2one(
        comodel_name='external.order.transaction',
        string='E-Commerce Transaction',
        domain="[('integration_id', '=', integration_id)]",
        copy=False,
    )
