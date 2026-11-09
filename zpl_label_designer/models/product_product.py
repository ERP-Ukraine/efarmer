from odoo import models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def _get_attribute(self, attr_name):
        """
        Get the value of the product attribute: the own value of the variant for attributes
        that create variants, values of the template for the rest.
        """
        self.ensure_one()

        attribute_values = self.product_template_attribute_value_ids
        attribute = attribute_values.attribute_id._find_by_name(attr_name)

        # Iterated instead of filtered(): it would lose the prefetch of the printed records
        # and read the value with a query per record
        for value in attribute_values:
            if value.attribute_id == attribute:
                return value.name

        # Attributes that don't create variants are not part of the variant combination,
        # so their values are taken from the product template
        return self.product_tmpl_id._get_attribute(attr_name)
