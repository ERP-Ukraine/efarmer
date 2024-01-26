# See LICENSE file for full copyright and licensing details.

from .product_abstract import ProductAbstractSend


class ProductProductSendMixin(ProductAbstractSend):
    """Specific behavior only for `product.product` Odoo class during sending to external."""

    def convert_to_external(self):
        self.ensure_odoo_record()

        attribute_values = []
        for attribute_value in self.odoo_obj.product_template_attribute_value_ids:
            attr_value = attribute_value.product_attribute_value_id
            if attr_value.exclude_from_synchronization:
                continue
            value = attr_value.to_export_format_or_export(self.integration)

            attribute_values.append(value)

        result = {
            'id': self.odoo_obj.id,
            'external_id': self.external_id,
            'attribute_values': attribute_values,
            'fields': self.calculate_send_fields(self.external_id)
        }
        return result
