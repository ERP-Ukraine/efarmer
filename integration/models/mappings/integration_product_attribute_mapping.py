# See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class IntegrationProductAttributeMapping(models.Model):
    _name = 'integration.product.attribute.mapping'
    _inherit = 'integration.mapping.mixin'
    _description = 'Integration Product Attribute Mapping'
    _mapping_fields = ('attribute_id', 'external_attribute_id')
    _mapping_label = 'Product Attribute'

    attribute_id = fields.Many2one(
        string='Odoo Product Attribute',
        comodel_name='product.attribute',
        ondelete='set null',
    )

    external_attribute_id = fields.Many2one(
        string='External Product Attribute',
        comodel_name='integration.product.attribute.external',
        required=True,
        ondelete='cascade',
    )

    @api.constrains('attribute_id', 'external_attribute_id')
    def _check_attribute_variant_mode(self):
        """Keep the external attribute's variant role consistent with the mapped Odoo
        attribute's "Variant Creation". An external attribute that is used to create
        product variants must map to an Odoo attribute that also creates variants, and
        one that is not must map to an Odoo attribute set to "Never". Enforced on both
        manual and automatic mappings, for every connector.
        """
        for mapping in self:
            odoo_attribute = mapping.attribute_id
            external_attribute = mapping.external_attribute_id

            if not odoo_attribute or not external_attribute:
                continue

            if bool(external_attribute.used_for_variants) == odoo_attribute.creates_variants:
                continue

            variant_creation = dict(
                odoo_attribute.fields_get(['create_variant'])['create_variant']['selection']
            ).get(odoo_attribute.create_variant, odoo_attribute.create_variant)

            if external_attribute.used_for_variants:
                raise ValidationError(_(
                    'The external attribute "%(external)s" is used to create product variants, '
                    'so it must be mapped to an Odoo attribute that also creates variants. The '
                    'Odoo attribute "%(odoo)s" has "Variant Creation" set to "%(mode)s", which '
                    'never creates variants.\n\n'
                    'Map it to an Odoo attribute whose "Variant Creation" is "Instantly" or '
                    '"Dynamically", or change the "Variant Creation" of "%(odoo)s".'
                ) % {
                    'external': external_attribute.name,
                    'odoo': odoo_attribute.name,
                    'mode': variant_creation,
                })

            raise ValidationError(_(
                'The external attribute "%(external)s" is a descriptive attribute that does not '
                'create product variants, so it must be mapped to an Odoo attribute with "Variant '
                'Creation" set to "Never". The Odoo attribute "%(odoo)s" has "Variant Creation" '
                'set to "%(mode)s".\n\n'
                'Map it to an Odoo attribute whose "Variant Creation" is "Never", or change the '
                '"Variant Creation" of "%(odoo)s".'
            ) % {
                'external': external_attribute.name,
                'odoo': odoo_attribute.name,
                'mode': variant_creation,
            })

    def run_import_attributes(self):
        external_attributes = self.mapped('external_attribute_id')
        action = external_attributes.run_import_attributes()
        return action
