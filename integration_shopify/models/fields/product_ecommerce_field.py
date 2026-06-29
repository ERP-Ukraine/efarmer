#  See LICENSE file for full copyright and licensing details.

import logging
from datetime import datetime, date

from odoo import api, models, fields, _
from odoo.exceptions import ValidationError
from odoo.addons.integration.tools import is_translated_value

from ...shopify_api import SHOPIFY


_logger = logging.getLogger(__name__)


def _stringify_metafield_value(value, odoo_field_type=None):
    """
    Coerce a single metafield value to a Shopify-ready string.

    Shopify metafield values must be strings. Falsy-but-meaningful numbers (``0``,
    ``0.0``) are kept, and only ``None`` / empty string map to ``''`` (which the
    adapter turns into a metafield delete).

    ``odoo_field_type`` is the type of the source Odoo field ('boolean', 'char',
    'integer', ...). It disambiguates values Odoo represents the same way - most
    importantly ``False``, which is both a real Boolean value and the "empty" value of
    Char/Text/relational fields. Add per-type branches here as new cases appear.

    Structured types (lists, money, dimensions, JSON) are expected to be produced as
    a ready string by an export script.
    """
    if value is None or value == '':
        return ''

    if isinstance(value, bool):
        # Only a real Boolean field carries a meaningful True/False; for any other
        # field type ``False`` is an empty value.
        if odoo_field_type == 'boolean':
            return 'true' if value else 'false'
        return 'true' if value else ''

    return str(value)


class ProductEcommerceField(models.Model):
    _inherit = 'product.ecommerce.field'

    type_api = fields.Selection(
        selection_add=[(SHOPIFY, 'Shopify')],
        ondelete={
            SHOPIFY: 'cascade',
        },
    )

    is_shopify_metafield = fields.Boolean(
        string='Metafield',
        default=False,
        help=(
            'Enable this for a Shopify metafield. The API Field Name must be formatted '
            'as "<namespace>.<key>" exactly as shown in Shopify (e.g. "custom.my_field").\n'
            'A metafield type is required for the field to be synced.'
        ),
    )

    shopify_metafield_type = fields.Selection(
        string='Metafield Type',
        selection=[
            ('boolean', 'Boolean'),
            ('color', 'Color'),
            ('date', 'Date'),
            ('date_time', 'Date Time'),
            ('dimension', 'Dimension'),
            ('json', 'JSON'),
            ('list.collection_reference', 'List Collection Reference'),
            ('list.color', 'List Color'),
            ('list.date', 'List Date'),
            ('list.date_time', 'List Date Time'),
            ('list.dimension', 'List Dimension'),
            ('list.file_reference', 'List File Reference'),
            ('list.metaobject_reference', 'List Metaobject Reference'),
            ('list.mixed_reference', 'List Mixed Reference'),
            ('list.number_integer', 'List Number Integer'),
            ('list.number_decimal', 'List Number Decimal'),
            ('list.page_reference', 'List Page Reference'),
            ('list.product_reference', 'List Product Reference'),
            ('list.rating', 'List Rating'),
            ('list.single_line_text_field', 'List Single Line Text Field'),
            ('list.url', 'List URL'),
            ('list.variant_reference', 'List Variant Reference'),
            ('list.volume', 'List Volume'),
            ('list.weight', 'List Weight'),
            ('money', 'Money'),
            ('multi_line_text_field', 'Multi Line Text Field'),
            ('number_decimal', 'Number Decimal'),
            ('number_integer', 'Number Integer'),
            ('rating', 'Rating'),
            ('rich_text_field', 'Rich Text Field'),
            ('single_line_text_field', 'Single Line Text Field'),
            ('url', 'URL'),
            ('volume', 'Volume'),
            ('weight', 'Weight'),
        ],
        default='single_line_text_field',
    )

    translation_key = fields.Char(
        string='Translation Key',
        copy=False,
        help='Key used for translations. If not set, the key will be the same as the field name.',
    )

    @api.constrains('is_shopify_metafield', 'technical_name', 'type_api')
    def _check_shopify_metafield_name(self):
        for rec in self:
            if rec.type_api != SHOPIFY or not rec.is_shopify_metafield:
                continue

            parts = (rec.technical_name or '').split('.')
            if len(parts) < 2 or not parts[-1] or not parts[-2]:
                raise ValidationError(_(
                    'The API Field Name "%s" is not a valid Shopify metafield reference.\n'
                    'Enter it as "<namespace>.<key>" exactly as shown in Shopify, '
                    'for example "custom.my_field".'
                ) % (rec.technical_name or ''))

    def get_translation_key(self, strip_path: bool = True):
        self.ensure_one()

        if self.translation_key:
            value = self.translation_key
        elif self.is_shopify_metafield:
            api_name = self.get_api_field_name()
            *__, namespace, key = api_name.split('.')
            value = f'metafields.{namespace}.{key}'
        else:
            value = self.get_api_field_name(strip_path=strip_path)

        return value

    def _build_import_field_dict(self, integration_id: int, data: tuple):
        _logger.info('%s: _build_import_field_dict: %s. Shopify inheritance.', integration_id, self.technical_name)
        self.ensure_one()

        if not self.is_shopify_metafield:
            return super()._build_import_field_dict(integration_id, data)

        template_data, variant_data = data

        if self.is_template_field:
            metafields = template_data['metafields']
        else:
            metafields = variant_data['metafields']

        api_name = self.get_api_field_name()
        *__, namespace, key = api_name.split('.')

        field = next(filter(lambda x: x['key'] == key and x['namespace'] == namespace, metafields), None)

        # An absent metafield means it was cleared on Shopify (Shopify deletes a metafield
        # when its value is emptied), so clear the mapped Odoo field instead of leaving the
        # previous value untouched.
        if not field:
            odoo_name = self.get_odoo_field_name(raise_if_not_found=False)
            return {odoo_name: False} if odoo_name else dict()

        value = self._format_metafield_input_type(field['value'])

        odoo_name = self.get_odoo_field_name(raise_if_not_found=True)

        return {odoo_name: value}

    def _prepare_metafield_export_value(self, integration_id: int, odoo_id: int):
        """
        Read the raw Odoo value and coerce it to a Shopify-ready metafield string.

        Metafield values must be strings, so we deliberately bypass the generic
        "Export Output Type" conversion (which would either send a non-string number
        or drop ``0`` / ``0.0`` / ``False`` to an empty string) and stringify the raw
        value directly - see ``_stringify_metafield_value``. Translatable values keep
        their per-language structure with each value stringified. Structured types
        (lists, money, dimensions, JSON) should be produced via an export script.
        """
        self.ensure_one()

        odoo_name = self.get_odoo_field_name()
        odoo_record = self.get_odoo_record(odoo_id)
        integration = self.env['sale.integration'].browse(integration_id)
        odoo_record = odoo_record.with_company(integration.company_id)

        odoo_field = odoo_record._fields.get(odoo_name)
        odoo_field_type = odoo_field.type if odoo_field else None

        value = odoo_record.convert_field_value_to_external(
            integration_id,
            odoo_name,
            translate=self.is_translatable_field,
        )

        if is_translated_value(value):
            return {
                'language': {
                    k: _stringify_metafield_value(v, odoo_field_type)
                    for k, v in value['language'].items()
                },
            }

        return _stringify_metafield_value(value, odoo_field_type)

    def _build_export_field_dict(self, integration_id: int, odoo_id: int):
        _logger.info('%s: _build_export_field_dict: %s. Shopify inheritance.', integration_id, self.technical_name)
        self.ensure_one()

        integration = self.env['sale.integration'].browse(integration_id)

        if not integration.is_integration_shopify:
            return super()._build_export_field_dict(integration_id, odoo_id)

        # TODO: this logic is too tricky and complex. Need to simplify it.

        force_export = self.env.context.get('integration_force_product_export')
        serialize_translations = self.env.context.get('integration_serialize_translations')

        # 1. Handle Shopify metafields special case
        if self.is_shopify_metafield:
            value = self._prepare_metafield_export_value(integration_id, odoo_id)

            if serialize_translations:
                # Skip sending empty value for unexported product (GQL error!)
                if force_export:
                    value_ = integration.adapter.parse_translated_value(value)
                    if not value_:
                        return {}

                key_ = self.get_translation_key()
                return {key_: value}

            # Always pass the metafield through, even when empty. The adapter decides
            # whether to set it (non-empty) or delete it (empty) while building the
            # product create/update mutation, so emptying a value clears the metafield.
            api_name = self.get_api_field_name()
            *__, namespace, key = api_name.split('.')

            values = {
                'key': key,
                'value': value,
                'namespace': namespace,
                'type': self.shopify_metafield_type,
            }

            return {'metafields': [values]}

        # 2. Handle regular fields
        value = super()._build_export_field_dict(integration_id, odoo_id)

        if not value:
            return {}

        # Skip sending empty value for unexported product (GQL error!)
        if force_export:
            value_ = integration.adapter.parse_translated_value(value)
            if not value_:
                return {}

        if serialize_translations:
            key_ = self.get_translation_key(strip_path=False)
            __, v = value.popitem()
            return {key_: v}

        return value

    def _format_metafield_input_type(self, value: str):
        if not value:
            return value

        odoo_field_type = self.import_field_type

        # Process metafields with Date and Datetime types. If corresponding Odoo fields have
        # Date or Datetime types, we need to convert the value to the string format.
        if self.shopify_metafield_type == 'date':
            # For metafields of type "date", the expected format is "YYYY-MM-DD".
            try:
                # Using date.fromisoformat here is fine because it validates the "YYYY-MM-DD" format.
                parsed_date = date.fromisoformat(value)
            except ValueError:
                raise ValidationError(
                    f'Date metafield "{self.name}" has incorrect date format: "{value}"'
                    ' (expected format: "YYYY-MM-DD")'
                )

            if odoo_field_type == 'date':
                return fields.Date.to_date(parsed_date)

            if odoo_field_type == 'datetime':
                # Odoo datetime field: combine the date with midnight (00:00:00) to form a datetime.
                datetime_value = datetime.combine(parsed_date, datetime.min.time())
                return fields.Datetime.to_datetime(datetime_value)

        elif self.shopify_metafield_type == 'date_time':
            # For metafields of type "date_time", the expected format is "YYYY-MM-DDTHH:MM:SSZ".
            try:
                # We use datetime.strptime instead of datetime.fromisoformat because fromisoformat does not
                # support the "Z" suffix, which indicates UTC
                parsed_datetime = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                raise ValidationError(
                    f'Datetime metafield "{self.name}" has incorrect datetime format: "{value}"'
                    ' (expected format: "YYYY-MM-DDTHH:MM:SSZ")'
                )

            if odoo_field_type == 'datetime':
                return fields.Datetime.to_datetime(parsed_datetime)

            if odoo_field_type == 'date':
                return fields.Date.to_date(parsed_datetime.date())

        return value
