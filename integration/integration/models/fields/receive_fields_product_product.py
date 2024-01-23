# See LICENSE file for full copyright and licensing details.

from .product_abstract import ProductAbstractReceive


class ProductProductReceiveMixin(ProductAbstractReceive):
    """Specific behavior only for `product.product` Odoo class during receiving from external."""

    def _get_template_attribute_values(self, template_id):
        ProductAttributeValue = self.env['product.attribute.value']
        ProductTemplateAttributeValue = self.env['product.template.attribute.value']
        template_attribute_value_ids = ProductTemplateAttributeValue.browse()

        for ext_attribute_value_id in self.get_ext_attr('attribute_value_ids'):
            if ext_attribute_value_id == '0':
                continue

            attribute_value_id = ProductAttributeValue.from_external(
                self.integration,
                ext_attribute_value_id,
            )

            template_attribute_value_ids |= ProductTemplateAttributeValue.search([
                ('product_attribute_value_id', '=', attribute_value_id.id),
                ('product_tmpl_id', '=', template_id),
            ])

        return template_attribute_value_ids
