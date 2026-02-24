from odoo import api, models
from odoo.exceptions import UserError
from odoo.tools import config


class ProductCategory(models.Model):
    _inherit = 'product.category'

    @api.model
    def create(self, vals):
        group_name = 'efarmer_sale_workflow.efarmer_sale_workflow_group_prod_categ_creator'
        if (not config['test_enable']
                and not config['test_file']
                and not self.env.user.has_group(group_name)):
            raise UserError("You're not allowed to create a product category.")

        return super().create(vals)
