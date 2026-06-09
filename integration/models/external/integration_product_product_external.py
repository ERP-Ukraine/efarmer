# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, _
from odoo.exceptions import UserError

from ...api.abstract_apiclient import AbsApiClient


class IntegrationProductProductExternal(models.Model):
    _name = 'integration.product.product.external'
    _inherit = ['integration.external.mixin', 'integration.product.external.mixin']
    _description = 'Integration Product Product External'
    _odoo_model = 'product.product'

    external_barcode = fields.Char(
        string='Barcode',
    )

    external_product_template_id = fields.Many2one(
        comodel_name='integration.product.template.external',
        string='External Product Template',
        ondelete='cascade',
    )

    external_attribute_value_ids = fields.Many2many(
        comodel_name='integration.product.attribute.value.external',
        relation='external_product_attribute_value_rel',
        column1='external_product_id',
        column2='external_attribute_value_id',
        string='External Attribute Values',
    )

    def apply_stock_levels(self, qty, location):
        self.ensure_one()

        variant = self.mapping_model.to_odoo(
            integration=self.integration_id,
            code=self.code,
        )

        if not variant.is_consumable_storable or variant.tracking != 'none':
            return variant, location, False

        StockQuant = self.env['stock.quant'].with_context(skip_inventory_export=True)

        # Set stock levels to zero
        inventory_locations = self.env['stock.location'].search([
            ('parent_path', 'like', location.parent_path + '%'),
            ('id', '!=', location.id)
        ])

        inventory_quants = StockQuant.search([
            ('location_id', 'in', inventory_locations.ids),
            ('product_id', '=', variant.id),
        ])

        inventory_quants.inventory_quantity = 0
        inventory_quants.action_apply_inventory()

        # Set new stock level
        inventory_quant = StockQuant.search([
            ('location_id', '=', location.id),
            ('product_id', '=', variant.id),
        ])

        if not inventory_quant:
            inventory_quant = StockQuant.create({
                'location_id': location.id,
                'product_id': variant.id,
            })

        float_qty = float(qty or False)
        inventory_quant.inventory_quantity = float_qty
        inventory_quant.action_apply_inventory()

        return variant, location, float_qty

    def _fix_unmapped(self, adapter_external_data):
        # We can't use this method, because products are imported by blocks
        pass

    def _post_import_external_one(self, adapter_external_record):
        """
        This method will receive individual variant record.
        And link external variant with external template.
        """
        template_code = adapter_external_record.get('ext_product_template_id')
        if not template_code:
            raise UserError(_(
                'The external product variant is missing the required "ext_product_template_id" field. '
                'This is a technical issue with the data received from the external system. '
                'Please contact our support team for assistance: https://support.ventor.tech/'
            ))

        external_template = self.env['integration.product.template.external'].search([
            ('code', '=', template_code),
            ('integration_id', '=', self.integration_id.id),
        ])

        if not external_template:
            raise UserError(_(
                'No external product template found with code "%s". It is possible that the products '
                'have not been imported yet. Please ensure the products are imported or contact support if needed.'
            ) % template_code)

        if len(external_template) > 1:
            raise UserError(_(
                'Multiple external product templates found for code "%s". This is a technical issue '
                'that requires investigation. Please contact our support team: https://support.ventor.tech/'
            ) % template_code)

        self.write({
            'external_barcode': adapter_external_record['barcode'],
            'external_product_template_id': external_template.id,
        })

    def format_recordset(self):
        values = self.mapped(
            lambda x: ', '.join([
                f'id={x.id}',
                f'code={x.code}',
                f'reference={x.external_reference}',
                f'barcode={x.external_barcode}',
                f'attribute_values={x.external_attribute_value_ids.mapped("code")}',
            ])
        )
        return '[%s]' % '; '.join(f'({x})' for x in values)

    def _search_suitable_variant(self):
        self.ensure_one()

        product = self.env[self._odoo_model]

        # Search by the reference
        if self.external_reference:
            product = self.external_product_template_id._find_product_by_field(
                self._odoo_model,
                self.integration_id.product_reference_name,
                self.external_reference,
            )

        # Search by the barcode
        if not product and self.external_barcode and self.integration_id.is_barcode_validation_required():
            product = self.external_product_template_id._find_product_by_field(
                self._odoo_model,
                self.integration_id.product_barcode_name,
                self.external_barcode,
            )

        return product

    def _find_suitable_variant(self, odoo_variant_ids):
        # 1. Map by reference
        variant = self._filter_variants_by_reference(odoo_variant_ids)

        # 2. Map by barcode
        if not variant:
            variant = self._filter_variants_by_barcode(odoo_variant_ids)

        # 3. Map by attributes
        if not variant:
            variant = self._filter_variants_by_attrs(odoo_variant_ids)

        return variant or self.env[self._odoo_model]

    def _filter_variants_by_reference(self, odoo_records):
        if not self.external_reference:
            return self.env[self._odoo_model]

        reference_field = self.integration_id.product_reference_name
        router = {getattr(x, reference_field): x for x in odoo_records}

        return router.get(self.external_reference)

    def _filter_variants_by_barcode(self, odoo_records):
        if not self.external_barcode:
            return self.env[self._odoo_model]

        barcode_field = self.integration_id.product_barcode_name
        router = {getattr(x, barcode_field): x for x in odoo_records}

        return router.get(self.external_barcode)

    def _filter_variants_by_attrs(self, odoo_records):
        attribute_value_ids = self.env['product.attribute.value']
        for external_value in self.external_attribute_value_ids:
            attribute_value_ids += external_value.odoo_record\
                .filtered(lambda x: not x.exclude_from_synchronization)

        result = list()

        for record in odoo_records:
            record_value_ids = record.product_template_attribute_value_ids\
                .mapped('product_attribute_value_id') \
                .filtered(lambda x: not x.exclude_from_synchronization)

            if (record_value_ids == attribute_value_ids):
                result.append(record)

        return result[0] if result else None

    def _create_internal_import_line(self):
        res = super()._create_internal_import_line()

        res.write({
            'origin_parent_id': self.external_product_template_id.id,
            'attribute_list': str(self.external_attribute_value_ids.mapped('code')),
        })

        return res

    def create_or_update_mapping(self, odoo_id=None):
        mapping = super().create_or_update_mapping(odoo_id=odoo_id)

        if odoo_id is not None:
            # (3, id, 0) - removes the record of <id> from the set, but does not delete it.
            # (4, id, 0) - adds an existing record of <id> to the set.
            mapping.odoo_record.with_context(skip_product_export=True).write({
                'integration_ids': [((4 if odoo_id else 3), self.integration_id.id, 0)],
            })

        return mapping

    def calculate_import_fields_data(self):
        self.ensure_one()

        integration = self.integration_id
        external_template = self.external_product_template_id
        __, variant_code = self.code.split('-')

        if variant_code == '0':
            return external_template.calculate_import_fields_data()

        template_data, variants_list, *__ = integration.adapter.get_product_for_import(external_template.code)

        __, variant_code = AbsApiClient._parse_product_external_code(self.code)
        variant_data = next(filter(lambda x: str(x['id']) == variant_code, variants_list), None)

        if not variant_data:
            raise UserError(_(
                '%s: No variant data found for product (%s). This is a technical issue that requires investigation.'
                ' Please contact our support team: https://support.ventor.tech/'
            ) % (integration.name, self.format_recordset()))

        product_variant = self.odoo_record

        return product_variant \
            .with_context(integration_first_time_import=(not product_variant)) \
            .calculate_import_fields_data(integration.id, template_data, variant_data)
