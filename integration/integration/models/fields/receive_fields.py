# See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo.models import BaseModel, _
from odoo.tools.sql import escape_psql
from ...exceptions import ApiImportError
from ...models.fields.common_fields import (
    BOOLEAN_FIELDS, FLOAT_FIELDS, TEXT_FIELDS, MANY2ONE_FIELDS,
)

from .common_fields import CommonFields
from ...tools import IS_FALSE


class ReceiveFields(CommonFields):

    def __call__(self, odoo_obj):
        self.odoo_obj = odoo_obj.sudo() if isinstance(odoo_obj, BaseModel) else odoo_obj
        return self

    def get_field_value(self, field_name):
        if not self.external_obj:
            return

        field = self._get_ecommerce_field(field_name)

        if field:
            return self.calculate_field_value(field).popitem()[1]

        return self._get_value(field_name)

    def get_ext_attr(self, ext_attr_name):
        return self._get_value(ext_attr_name)

    def _get_value(self, field_name):
        return self.external_obj.get(field_name)

    def convert_translated_field_to_odoo_format(self, value):
        if not (isinstance(value, dict) and value.get('language')):
            return value

        language_mappings = self.env['integration.res.lang.mapping'].search([
            ('integration_id', '=', self.integration.id),
        ])

        language_codes = {x.external_language_id.code: x.language_id.id for x in language_mappings}

        if isinstance(value['language'], dict):
            value['language'] = [value['language']]

        result = {}

        for translation in value['language']:
            external_language_id = translation['attrs']['id']

            if external_language_id in language_codes:
                result[language_codes[external_language_id]] = translation['value']

        return {'language': result}

    def _get_simple_value(self, ecommerce_field):
        field_name = ecommerce_field.odoo_field_id.name
        ext_value = self._get_value(ecommerce_field.technical_name)

        return {field_name: self._prepare_simple_value(ecommerce_field, ext_value)}

    def _prepare_simple_value(self, ecommerce_field, ext_value):
        field_type = ecommerce_field.odoo_field_id.ttype

        if field_type in BOOLEAN_FIELDS:
            return ext_value and ext_value != IS_FALSE or False
        if field_type in FLOAT_FIELDS:
            return ext_value and float(ext_value) or 0
        if field_type in TEXT_FIELDS:
            return ext_value or None
        if field_type in MANY2ONE_FIELDS:
            if not ext_value or ext_value == IS_FALSE:
                return False
            odoo_model = self.env[ecommerce_field.odoo_field_id.relation]

            result = odoo_model.search([(odoo_model._rec_name, '=ilike', escape_psql(ext_value))])

            if not result:
                result = odoo_model.create({odoo_model._rec_name: ext_value})

            return result[0].id

        return ext_value

    def _get_translatable_field_value(self, ecommerce_field):
        api_name = ecommerce_field.technical_name
        erp_name = ecommerce_field.odoo_field_id.name

        api_value = self._get_value(api_name)
        erp_value = self.convert_translated_field_to_odoo_format(api_value)

        return {
            erp_name: erp_value,
        }

    def _get_python_method_value(self, ecommerce_field):
        result = self._compute_field_value_using_python_method(
            ecommerce_field.receive_method, ecommerce_field.odoo_field_id.name)
        return result

    def calculate_receive_fields(self):
        domain_ext = self.odoo_obj and [('receive_on_import', '=', True)] or []
        vals = self.calculate_fields(domain_ext)

        if not self.odoo_obj:
            vals['active'] = True
        return vals

    def find_attributes_in_odoo(self, ext_attribute_value_ids):
        ProductAttributeValue = self.env['product.attribute.value']
        attr_values_ids_by_attr_id = defaultdict(list)
        attribute_value_ids = ProductAttributeValue

        for ext_attribute_value_id in ext_attribute_value_ids:
            attribute_value_ids |= ProductAttributeValue.from_external(
                self.integration, ext_attribute_value_id)

        for attribute_value_id in attribute_value_ids:
            attribute_id = attribute_value_id.attribute_id.id
            attr_values_ids_by_attr_id[attribute_id].append(attribute_value_id.id)

        return attr_values_ids_by_attr_id

    def find_categories_in_odoo(self, ext_category_ids):
        ProductPublicCategory = self.env['product.public.category']
        odoo_categories = ProductPublicCategory

        for external_category_id in ext_category_ids:
            if external_category_id:
                odoo_categories |= ProductPublicCategory.from_external(
                    self.integration, external_category_id)

        return odoo_categories.ids

    def convert_from_external(self):
        return self.calculate_receive_fields()

    def convert_weight_uom_to_odoo(self, weight, uom_name):
        return self._convert_weight_uom(weight, uom_name, True)

    def _get_odoo_tax_from_external(self, tax_value):
        erp_tax = self.integration.convert_external_tax_to_odoo(tax_value)
        if not erp_tax:
            raise ApiImportError(_(
                'It is not possible to import product into Odoo for "%s" integration. '
                'External tax value "%s" may not be converted to the relevant odoo value.'
            ) % (self.integration.name, tax_value))

        return erp_tax

    def _create_product_incoming_line(self):
        ref_field = self.integration._get_product_reference_name()
        barcode_field = self.integration._get_product_barcode_name()

        vals = {
            'code': self._get_value('id'),
            'reference': self.get_field_value(ref_field),
            'barcode': self.get_field_value(barcode_field),
            'model_name': self.odoo_obj._name,
            'type': 'incoming',
        }

        if self.is_variant:
            vals.update(
                code=self.get_ext_attr('variant_id'),
                attribute_list=str(self.get_ext_attr('attribute_value_ids')),
            )

        return self.env['import.product.line'].create(vals)
