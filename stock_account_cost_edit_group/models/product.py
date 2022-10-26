from odoo import models, _
from odoo.exceptions import AccessError


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def write(self, vals):
        # allow automatic cost change managed by costing method
        # runs with sudo() environment
        if self.env.su or 'standard_price' not in vals:
            return super(ProductProduct, self).write(vals)

        cost_edit_group_name = 'stock_account_cost_edit_group.group_can_edit_product_cost'
        user_can_edit_cost = self.env.user.has_group(cost_edit_group_name)

        if not user_can_edit_cost:
            cost_group = self.env.ref(cost_edit_group_name)
            raise AccessError(_('Only users belonging to the "%(group_name)s" group can modify product cost.',
                                group_name=cost_group.name))
        return super(ProductProduct, self).write(vals)

