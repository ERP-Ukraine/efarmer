# See LICENSE file for full copyright and licensing details.

import logging

from odoo import fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _


_logger = logging.getLogger(__name__)


class IntegrationProductTemplateMapping(models.Model):
    _name = 'integration.product.template.mapping'
    _inherit = 'integration.mapping.mixin'
    _description = 'Integration Product Template Mapping'
    _mapping_fields = ('template_id', 'external_template_id')
    _mapping_label = 'Product Template'

    template_id = fields.Many2one(
        string='Odoo Product',
        comodel_name='product.template',
        ondelete='cascade',
    )

    external_template_id = fields.Many2one(
        string='E-Commerce Product',
        comodel_name='integration.product.template.external',
        required=True,
        ondelete='cascade',
    )

    _uniq = models.Constraint(
        'unique(integration_id, template_id, external_template_id)',
        '',
    )

    def run_map_product(self):
        self.ensure_one()
        return self.integration_id.import_external_product(self.external_template_id.code)

    def run_import_products(self):
        return self.mapped('external_template_id').run_import_products()

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
            if 'template_id' in vals and rec.env.context.get('product_template_mapping'):
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

    def action_reimport_products(self):
        external_ids = []
        integration = self.mapped('integration_id')
        if len(integration) > 1:
            raise UserError(_(
                'Selected products have different integrations.\n'
                'Please select products from the same integration.'
            ))

        records = self.filtered(lambda x: not x.template_id)
        external_ids = records.mapped('external_template_id.code')

        integration.import_products_in_background(external_ids)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Reimport Product'),
                'message': _('Products import jobs are created'),
                'type': 'success',
                'sticky': False,
            }
        }

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

    def calculate_import_data(self):
        self.ensure_one()

        external_template = self.external_template_id
        if not external_template:
            return {}

        data = external_template.calculate_import_fields_data()

        data['products'] = []
        for variant in external_template.external_product_variant_ids:
            data['products'].append(
                variant.calculate_import_fields_data()
            )

        if self.env.context.get('integration_return_action'):
            return self.env['message.wizard'].create_json_and_run(data)

        return data

    def calculate_export_data(self):
        self.ensure_one()

        template = self.template_id
        if not template:
            return {}

        data = template.to_export_format(self.integration_id)

        if self.env.context.get('integration_return_action'):
            return self.env['message.wizard'].create_json_and_run(data)

        return data

    def action_open_external_product(self):
        """
        Open the product in the e-commerce system.
        """
        self.ensure_one()

        if not self.external_template_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': 'No external product template found.',
                    'type': 'warning',
                    'sticky': False,
                }
            }

        return self.external_template_id.action_open_external_product()
