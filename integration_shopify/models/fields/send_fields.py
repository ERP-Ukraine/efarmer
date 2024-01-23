# See LICENSE file for full copyright and licensing details.

from ...shopify_api import METAFIELDS_NAME
from odoo.addons.integration.exceptions import ApiExportError
from odoo.addons.integration.models.fields import SendFields
from odoo import _


class SendFieldsShopify(SendFields):

    def convert_translated_field_to_integration_format(self, field_name):
        external_code = self.adapter.lang
        language = self.env['res.lang'].from_external(self.integration, external_code)

        return getattr(self.odoo_obj.with_context(lang=language.code), field_name)

    def _get_simple_value(self, ecommerce_field):
        result = super(SendFieldsShopify, self)._get_simple_value(ecommerce_field)

        field_name = result and list(result.keys())[0] or ''

        if field_name.startswith(f'{METAFIELDS_NAME}.'):
            if not ecommerce_field.shopify_metafield_type:
                raise ApiExportError(_(
                    'For export metafield "%s" we need "namespace" and "type". Please, fill it '
                    'in e-Commerce Integration->Product Fields->All Product Fields. '
                    'You can find them in Shopify Settings->Custom Data->Products') % field_name)

            __, namespace, key = field_name.split('.')
            meta_value = {
                'key': key,
                'value': result[field_name],
                'namespace': namespace,
                'type': ecommerce_field.shopify_metafield_type,
            }
            result[field_name] = meta_value

        return result

    def _update_calculated_fields(self, vals, field_values):
        for field_name, field_value in field_values.items():
            if field_name.startswith(f'{METAFIELDS_NAME}.'):
                field_name = METAFIELDS_NAME
                field_value = vals.get(METAFIELDS_NAME, []) + [field_value]

            vals[field_name] = field_value

        return vals
