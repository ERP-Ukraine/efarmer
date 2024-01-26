# See LICENSE file for full copyright and licensing details.

from odoo import fields, models
import logging


_logger = logging.getLogger(__name__)


class IntegrationProductTemplateMapping(models.Model):
    _name = 'integration.product.template.mapping'
    _inherit = 'integration.mapping.mixin'
    _description = 'Integration Product Template Mapping'
    _mapping_fields = ('template_id', 'external_template_id')

    template_id = fields.Many2one(
        comodel_name='product.template',
        ondelete='cascade',
    )

    external_template_id = fields.Many2one(
        comodel_name='integration.product.template.external',
        required=True,
        ondelete='cascade',
    )

    _sql_constraints = [
        ('uniq', 'unique(integration_id, template_id, external_template_id)', '')
    ]

    def run_map_product(self):
        self.ensure_one()
        return self.integration_id.import_external_product(self.external_template_id.code)

    def run_import_products(self, import_images=False):
        import_images = self.env.context.get('import_images') or import_images
        external_ids = self.mapped('external_template_id')
        if not external_ids:
            return False
        return external_ids.run_import_products(import_images)

    def _auto_mapping_product_product(self):
        """
        Auto mapping product_product
        """
        self.ensure_one()

        product_product_mapping = self.get_product_mapping_from_parent_external()
        if not product_product_mapping or \
                self._check_product_identity(product_product_mapping) or \
                len(product_product_mapping) > 1:
            _logger.info('Auto mapping of the product_product did not happen')
            return False

        if self.template_id:
            product_product_mapping.product_id = self.template_id.product_variant_id
            log_msg = 'Auto mapping variant %s' % product_product_mapping.product_id.name or ''
        else:
            log_msg = 'Auto unlinking variant %s' % product_product_mapping.product_id.name or ''
            product_product_mapping.product_id = False
        _logger.info(log_msg)
        return True

    def write(self, vals):
        res = super(IntegrationProductTemplateMapping, self).write(vals)
        for rec in self:
            if 'template_id' in vals and rec._context.get('product_template_mapping'):
                rec._auto_mapping_product_product()
        return res

    def get_product_mapping_from_parent_external(self):
        """
        Get product_product_mapping
        """
        self.ensure_one()

        ProductProductMapping = self.env['integration.product.product.mapping']
        product_product_external = self.external_template_id.external_product_variant_ids
        if len(product_product_external) != 1:
            return False

        product_product_mapping_id = ProductProductMapping.search([
            ('integration_id', '=', self.integration_id.id),
            ('external_product_id', '=', product_product_external.id),
        ])

        return product_product_mapping_id

    def _check_product_identity(self, product_product_mapping):
        """
        Check product identity
        """
        self.ensure_one()
        result = False

        if product_product_mapping and self.template_id:
            if self.template_id.product_variant_id == product_product_mapping.product_id:
                result = True

        return result
