#  See LICENSE file for full copyright and licensing details.

import logging
from datetime import datetime, date

from odoo import models, fields
from odoo.exceptions import ValidationError

from ...shopify_api import SHOPIFY


_logger = logging.getLogger(__name__)


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
        compute='_compute_is_shopify_metafield',
        help=(
            'Shopify metafield have to be formatted as <Namespace>.<Key>\n'
            'Metafield type is required for metafield to be synced.'
        ),
    )

    shopify_metafield_type = fields.Selection(
        string='Metafield Type',
        selection=[
            ('date', 'Date'),
            ('boolean', 'Boolean'),
            ('date_time', 'DateTime'),
            ('number_decimal', 'Number Decimal'),
            ('number_integer', 'Number Integer'),
            ('multi_line_text_field', 'Multi Line Text Field'),
            ('single_line_text_field', 'Single Line Text Field'),
        ],
        default='single_line_text_field',
    )

    translation_key = fields.Char(
        string='Translation Key',
        copy=False,
        help='Key used for translations. If not set, the key will be the same as the field name.',
    )

    def _compute_is_shopify_metafield(self):
        for rec in self:
            rec.is_shopify_metafield = (rec.type_api == SHOPIFY) and rec.technical_name.startswith('metafields.')

    def get_translation_key(self, field_name_only: bool = True):
        self.ensure_one()

        if self.translation_key:
            value = self.translation_key
        elif self.is_shopify_metafield:
            api_name = self.get_api_field_name()
            *__, namespace, key = api_name.split('.')
            value = f'metafields.{namespace}.{key}'
        else:
            value = self.get_api_field_name(field_name_only=field_name_only)

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

        if not field:
            return dict()

        value = self._format_metafield_input_type(field['value'])

        odoo_name = self.get_odoo_field_name(raise_if_not_found=True)

        return {odoo_name: value}

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
            value = self._prepare_export_value(integration_id, odoo_id)

            # Skip sending empty value for unexported product (GQL error!)
            if force_export:
                value_ = integration.adapter.parse_translated_value(value)
                if not value_:
                    return {}

            if serialize_translations:
                key_ = self.get_translation_key()
                return {key_: value}

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
            key_ = self.get_translation_key(field_name_only=False)
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
