from odoo import api, models
from odoo.exceptions import Warning as oWarning


class ProductCategory(models.Model):
    _inherit = 'product.category'

    @api.model
    def create(self, vals):
        group_name = 'efarmer_sale_workflow.efarmer_sale_workflow_group_prod_categ_creator'
        if not self.env.user.has_group(group_name):
            raise oWarning("You're not allowed to create a product category.")

        return super().create(vals)
