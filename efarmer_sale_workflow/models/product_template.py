from odoo import api, models
from odoo.exceptions import Warning as oWarning


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    @api.model
    def create(self, vals):
        group_name = 'efarmer_sale_workflow.efarmer_sale_workflow_group_prod_categ_creator'
        if not self.env.user.has_group(group_name):
            raise oWarning("You're not allowed to create a product.")

        return super().create(vals)
