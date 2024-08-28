# See LICENSE file for full copyright and licensing details.

from odoo import _
from odoo.exceptions import UserError

from .product_abstract import ProductAbstractSend
from ...exceptions import NotMappedToExternal


class ProductTemplateSendMixin(ProductAbstractSend):
    """Specific behavior only for `product.template` Odoo class during sending to external."""

    def variant_converter(self):
        if not self._sub_converter:
            converter = self.env['product.product']\
                .init_variant_export_converter(self.integration)
            self._sub_converter = converter
        return self._sub_converter

    def ensure_template_mapped(self):
        tmpl_ok = self.ensure_mapped()
        converter = self.variant_converter()
        variant_ok = all(
            x.ensure_mapped() for x in map(lambda x: converter(x), self.get_variants())
        )
        return tmpl_ok and variant_ok

    def convert_to_external(self):
        variant_ids = self.get_variants()
        converter = self.variant_converter()

        result = {
            'id': self.odoo_obj.id,
            'external_id': self.external_id,
            'type': self.odoo_obj.type,
            'kits': self._get_kits(),
            'products': [converter(x).convert_to_external() for x in variant_ids],
            'variant_count': len(variant_ids),
            'fields': self.calculate_send_fields(self.external_id),
        }

        result_upd = self.odoo_obj._template_converter_update(
            result,
            self.integration,
            self.external_id,
        )
        return result_upd

    def convert_pricelists(self, pricelist_ids=None, item_ids=None, raise_error=False):
        force_sync_pricelist = self.odoo_obj.to_force_sync_pricelist
        if force_sync_pricelist:
            pricelist_ids = item_ids = None

        def _format_result(converter, prices):
            return (
                converter.odoo_obj.id,
                converter.odoo_obj._name,
                converter.external_id,
                prices,
                force_sync_pricelist,
            )

        t_prices_list = self._collect_specific_prices(
            pricelist_ids=pricelist_ids,
            item_ids=item_ids,
            raise_error=raise_error,
        )
        variant_ids = self.get_variants()
        converter = self.variant_converter()

        variant_data_list = list()
        for variant in variant_ids:
            x_converter = converter(variant)
            x_converter.ensure_external_code()

            v_prices_list = x_converter._collect_specific_prices(
                pricelist_ids=pricelist_ids,
                item_ids=item_ids,
                raise_error=raise_error,
            )
            if force_sync_pricelist or v_prices_list:
                variant_data = _format_result(x_converter, v_prices_list)
                variant_data_list.append(variant_data)

        if force_sync_pricelist or t_prices_list or variant_data_list:
            tmpl_data = _format_result(self, t_prices_list)
            return tmpl_data, variant_data_list

        return tuple()

    def get_variants(self):
        """
            Returns a sorted recordset of product variants filtered by integration.

            The method filters the product variant records based on their integration_ids and
                sorts them based on their
            attribute values. The sorting is done in the following order:
                1. The attribute ID of the attribute value
                2. The sequence number of the attribute value.

            Returns:
                recordset: A sorted recordset of product variants filtered by integration.
        """
        variants = self.odoo_obj.product_variant_ids.filtered(
            lambda x: self.integration in x.integration_ids).sorted(
            key=lambda v: [
                (attr.attribute_id.id, attr.sequence)
                for attr in
                v.product_template_attribute_value_ids.mapped('product_attribute_value_id')
            ])

        return variants

    def _get_kits(self):
        kits = self.env['mrp.bom'].search([
            ('product_tmpl_id', '=', self.odoo_obj.id),
            ('type', '=', 'phantom'),
            ('company_id', 'in', (self.integration.company_id.id, False)),
        ])

        kits_data = []
        for kit in kits:
            component_list = []

            for bom_line in kit.bom_line_ids:
                try:
                    external_record = bom_line.product_id.to_external_record(self.integration)
                except NotMappedToExternal as ex:
                    raise UserError(
                        _('Awaiting export of the "%s" product.\n%s')
                        % (bom_line.product_id.display_name, ex.args[0])
                    )

                component_list.append({
                    'qty': bom_line.product_qty,
                    'name': bom_line.display_name,
                    'product_id': external_record.code,
                    'external_reference': external_record.external_reference,
                })

            kits_data.append(dict(components=component_list))

        return kits_data

    def send_price(self, field_name):
        if self.integration.integration_pricelist_id:
            price = self.integration.integration_pricelist_id.get_product_price(
                self.odoo_obj, 0, False,
            )
        else:
            price = self.odoo_obj.list_price
        return {
            field_name: str(self.get_price_by_send_tax_incl(price)),
        }

    def send_integration_name(self, field_name):
        return {
            field_name: self.odoo_obj.get_integration_name(self.integration),
        }
