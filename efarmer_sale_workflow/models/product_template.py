from odoo import api, models, fields
from odoo.exceptions import UserError
from odoo.tools import config


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    description_labels = fields.Text('Description for Product Labels', translate=True)

    @api.model
    def create(self, vals):
        group_name = 'efarmer_sale_workflow.efarmer_sale_workflow_group_prod_categ_creator'
        if not self.env.user.has_group(group_name):
            # do not break odoo test
            if not config['test_enable'] and not config['test_file']:
                raise UserError("You're not allowed to create a product.")

        return super().create(vals)
