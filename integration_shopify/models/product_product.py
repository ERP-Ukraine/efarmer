# See LICENSE file for full copyright and licensing details.

from odoo import models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def get_integration_cost_price(self, integration):
        self.ensure_one()
        if self.product_tmpl_id.product_variant_count > 1:
            return self.standard_price
        return self.product_tmpl_id.standard_price
