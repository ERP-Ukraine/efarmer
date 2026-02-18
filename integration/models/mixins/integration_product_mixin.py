# See LICENSE file for full copyright and licensing details.

import ast
from lxml import etree

from odoo import models, _
from odoo.exceptions import UserError

from ...tools import round_float, MergeableDict
from ...exceptions import NotMappedToExternal


class IntegrationProductMixin(models.AbstractModel):
    _name = 'integration.product.mixin'
    _description = 'Integration Product Mixin'

    _image_name = None
    _image_names = None

    @property
    def is_template(self):
        return self._name == 'product.template'

    @property
    def is_consumable_storable(self):
        return self.type == 'consu' and self.is_storable

    def to_external_record(self, integration, raise_error=True):
        """
        Redefined method from the integration.model.mixin
        because of integration_mapping_ids field exists
        """
        self.ensure_one()

        mapping = self.integration_mapping_ids\
            .filtered(lambda x: x.integration_id.id == integration.id)[-1:]

        if not mapping and raise_error:
            raise NotMappedToExternal(
                _('Can\'t map odoo value to external code'),
                self._name,
                self.id,
                integration,
            )

        return mapping.external_record

    def to_external(self, integration):
        """Redefined method from the integration.model.mixin"""
        external = self.to_external_record(integration)
        return external.code

    def calculate_import_fields_data(
        self,
        integration_id: int,
        template_data: dict,
        variant_data: dict = None,
        add_domain: list = None,
    ) -> dict:

        domain_ext = []
        if not self.env.context.get('integration_first_time_import'):
            domain_ext.append(('import_enabled', '=', True))
        domain_ext.extend(add_domain or [])
        domain_ext = list(set(domain_ext))

        result = {}
        for field_mapping in self._get_ecommerce_fields_mappings(integration_id, domain_ext):
            value = field_mapping.calculate_import_value(template_data, variant_data, odoo_id=self.id)
            result.update(value)

        return result

    def calculate_export_fields_data(
        self,
        integration_id: int,
        add_domain: list = None,
    ) -> dict:
        self.ensure_one()

        domain_ext = []
        if not self.env.context.get('integration_force_product_export'):
            domain_ext.append(('export_enabled', '=', True))

        domain_ext.extend(add_domain or [])
        domain_ext = list(set(domain_ext))

        mappings = self._get_ecommerce_fields_mappings(integration_id, domain_ext)

        mergeable_dict = MergeableDict()
        for mapping in mappings:
            value = mapping.calculate_export_value(self.id)
            mergeable_dict.merge(**value)

        return mergeable_dict.dump()

    def convert_field_value_to_external(self, integration_id: int, field_name: str, translate: bool = False):
        self.ensure_one()

        if translate:
            value = self.convert_field_translations_to_external(
                integration_id,
                field_name,
            )
        else:
            value = self.get_field_value_in_store_language(
                integration_id,
                field_name,
            )

        return value

    def _get_extra_images(self):
        return getattr(self, self._image_names)

    def action_integration_mappings(self):
        """Open a list view with mappings for the current product"""
        mapping_ids = self.mapped('integration_mapping_ids')

        return {
            'type': 'ir.actions.act_window',
            'name': 'Product Mappings',
            'res_model': mapping_ids._name,
            'view_mode': 'list',
            'domain': [('id', 'in', mapping_ids.ids)],
            'target': 'current',
        }

    def get_price_by_send_tax_incl(self, integration_id: int, price: float) -> float:
        if not price:
            return 0

        # Get the decimal precision value from the integration settings
        integration = self.env['sale.integration'].browse(integration_id)
        decimal_precision = integration.get_settings_value('decimal_precision')
        try:
            decimal_precision = int(decimal_precision)
        except ValueError:
            raise UserError(_(
                'The "decimal_precision" value is not a valid integer.\n'
                'To resolve this issue, please follow these steps:\n'
                '1. Go to "E-Commerce Integrations → Stores → %s → General tab → Parameters table".\n'
                '2. Locate the parameter named "decimal_precision".\n'
                '3. Enter a valid integer value for the "decimal_precision" parameter.'
            ) % integration.name)

        if integration.select_send_sale_price == 'no_changes':
            return round_float(price, decimal_precision)

        # Calculate the price rounding based on the decimal precision
        precision_rounding = 10 ** (-decimal_precision)

        # In some cases, it is necessary to force/prevent the rounding of the tax and the total
        # amounts. For example, in SO/PO line, we don't want to round the price unit at the
        # precision of the currency.
        # The context key 'round' allows to force the standard behaviour.
        # We also pass the context variable 'precision_rounding' to indicate the rounding precision.
        ctx = dict(round=False)
        if self.env.company.currency_id.rounding > precision_rounding:
            # If precision_rounding is greater than the currency's rounding precision,
            # update the context to use the custom precision for rounding.
            ctx.update(precision_rounding=precision_rounding)

        res = self.taxes_id\
            .filtered(lambda x: x.company_id == integration.company_id) \
            .with_context(**ctx) \
            .compute_all(price, product=self, partner=self.env['res.partner'])

        if integration.select_send_sale_price == 'tax_included':
            return round_float(res['total_included'], decimal_precision)

        return round_float(res['total_excluded'], decimal_precision)

    def _get_ecommerce_fields_mappings(self, integration_id: int, domain_ext: list):
        search_domain = [
            ('active', '=', True),
            ('integration_id', '=', integration_id),
            ('odoo_model_name', '=', self._name),
            *domain_ext,
        ]
        return self.env['product.ecommerce.field.mapping'].search(search_domain)

    def _collect_specific_prices(self, integration_id: int, pricelist_ids=None, item_ids=None, raise_error=False):
        result = list()
        integration = self.env['sale.integration'].browse(integration_id)

        if item_ids:
            x_item_ids = self._search_pricelist_items(i_ids=item_ids)
        else:
            x_pricelist_ids = pricelist_ids or integration._search_pricelist_mappings()
            x_item_ids = self._search_pricelist_items(p_ids=x_pricelist_ids)

        if not x_item_ids:
            return result

        for rec in x_item_ids:
            vals = rec.to_export_format(integration, self._name, raise_error=raise_error)
            result.append(vals)

        return result

    def _exclude_convert_to_webp_option(self, arch: str, xpath_str: str) -> str:
        if not (self.skip_convert_to_webp() and 'convert_to_webp' in arch):
            return arch

        arch_tree = etree.fromstring(arch)

        for node_field in arch_tree.xpath(xpath_str):
            options_str = node_field.get('options')

            if options_str:
                options = ast.literal_eval(options_str)
                options.pop('convert_to_webp', None)

                node_field.set('options', repr(options))

        return etree.tostring(arch_tree, encoding='unicode')

    def skip_convert_to_webp(self):
        """ Get skip convert to webp flag. """
        value = self.env['ir.config_parameter'].sudo().get_param('integration.skip_convert_to_webp')

        try:
            return int(value) == 1
        except (ValueError, TypeError):
            return False
