# See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _
import logging


_logger = logging.getLogger(__name__)


class IntegrationProductProductMapping(models.Model):
    _name = 'integration.product.product.mapping'
    _inherit = 'integration.mapping.mixin'
    _description = 'Integration Product Product Mapping'
    _mapping_fields = ('product_id', 'external_product_id')

    product_id = fields.Many2one(
        comodel_name='product.product',
        ondelete='cascade',
    )

    external_product_id = fields.Many2one(
        comodel_name='integration.product.product.external',
        required=True,
        ondelete='cascade',
    )

    _sql_constraints = [
        ('uniq', 'unique(integration_id, product_id, external_product_id)', '')
    ]

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if not self.product_id:
            return

        product_template_external = self.external_product_id.external_product_template_id
        product_product_external = product_template_external.external_product_variant_ids
        if len(product_product_external) <= 1:
            return

        product_template_mapping = self.get_template_mapping_from_parent_external()
        if not product_template_mapping:
            return

        if self.product_id.product_tmpl_id != product_template_mapping.template_id:
            return {
                'warning': {
                    'title': _('Warning'),
                    'message': _('You are linking External Variant \'%s\' to Odoo Variant - '
                                 '\'%s\'. \n But the same External Product has other '
                                 'variants, that are linked to Odoo Products belonging to '
                                 'different Odoo Template.\n\t%s \n\nSelected Odoo '
                                 'Variant is linked to Odoo Template \'(%s)%s\' and other '
                                 'external variants are linked to different Odoo Template '
                                 '\'%s\'. \nPlease, make sure that this is expected '
                                 'behaviour as this may lead to data inconsistency.'
                                 ) % (
                        self.external_product_id.display_name,
                        self.product_id.display_name,
                        ',\n\t'.join([v.display_name for v in product_product_external]),
                        self.product_id.product_tmpl_id.id,
                        self.product_id.product_tmpl_id.display_name,
                        product_template_mapping.external_template_id.display_name,)
                }}

    def write(self, vals):
        res = super(IntegrationProductProductMapping, self).write(vals)
        for rec in self:
            if 'product_id' in vals and rec._context.get('product_product_mapping'):
                rec._auto_mapping_product_template()
        return res

    def _check_template_identity(self, product_template_mapping):
        """
        Check template identity
        """
        self.ensure_one()
        result = False

        if product_template_mapping and self.product_id:
            if product_template_mapping.template_id == self.product_id.product_tmpl_id:
                result = True

        return result

    def get_template_mapping_from_parent_external(self):
        """
        Get product_template_mapping
        """
        self.ensure_one()

        ProductTemplateMapping = self.env['integration.product.template.mapping']
        product_template_external = self.external_product_id.external_product_template_id

        product_template_mapping_ids = ProductTemplateMapping.search([
            ('integration_id', '=', self.integration_id.id),
            ('external_template_id', '=', product_template_external.id),
        ])

        return product_template_mapping_ids

    def _auto_mapping_product_template(self):
        """
        Auto mapping product_template
        """
        self.ensure_one()

        product_product_external_ids = self.external_product_id.external_product_template_id \
            .external_product_variant_ids

        product_template_mapping = self.get_template_mapping_from_parent_external()

        if not product_template_mapping:
            _logger.info('Product Template Mapping not found for %s' % self.product_id.display_name)
            return False

        if self._check_template_identity(product_template_mapping):
            _logger.info('Product Template Mapping already exists')
            return False

        if len(product_product_external_ids) > 1:
            product_mapping = self.env['integration.product.product.mapping'].search([
                ('integration_id', '=', self.integration_id.id),
                ('external_product_id', 'in', product_product_external_ids.ids),
            ])

            product_ids = self.env['integration.product.product.mapping']
            if self.product_id:
                product_ids |= product_mapping.filtered(
                    lambda r: r.product_id.product_tmpl_id == self.product_id.product_tmpl_id
                )
            else:
                product_ids |= product_mapping.filtered(lambda r: not r.product_id)

            if len(product_ids) < len(product_product_external_ids):
                return False

        if self.product_id:
            product_template_mapping.template_id = self.product_id.product_tmpl_id
            _logger.info('Auto mapping product_template: %s',
                         product_template_mapping.template_id.name)
        else:
            product_template_mapping.template_id = False
            _logger.info('Auto zeroing product_template: %s',
                         product_template_mapping.template_id.name)
        return True
