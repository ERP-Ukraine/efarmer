# See LICENSE file for full copyright and licensing details.

from odoo import models


class AccountTaxGroup(models.Model):
    _name = 'account.tax.group'
    _inherit = ['account.tax.group', 'integration.model.mixin']

    def to_external(self, integration):
        if integration.is_shopify():
            return False

        return super(AccountTaxGroup, self).to_external(integration)
