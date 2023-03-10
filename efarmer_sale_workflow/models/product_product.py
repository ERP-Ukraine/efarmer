# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html

from odoo import models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def get_product_multiline_description_sale(self):
        """ Override method to display the product.template name instead
            of the product.product name in SO line Description (name)
        """
        super().get_product_multiline_description_sale()
        name = self.product_tmpl_id.display_name
        if self.description_sale:
            name += '\n' + self.description_sale

        return name
