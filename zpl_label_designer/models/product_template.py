from odoo import models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    def _get_attribute(self, attr_name):
        """
        Get values of the template attribute (comma-separated if there are several values).
        """
        self.ensure_one()

        attribute_lines = self.attribute_line_ids
        attribute = attribute_lines.attribute_id._find_by_name(attr_name)

        if not attribute:
            return ''

        # Values are filtered instead of lines: values of all printed templates are read by
        # one query, while filtered lines would read them with a query per template
        values = attribute_lines.value_ids.filtered(lambda value: value.attribute_id == attribute)

        return ', '.join(values.mapped('name'))
