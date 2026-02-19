# See LICENSE file for full copyright and licensing details.

import logging
import re
import json

from odoo import api, models, fields, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools.safe_eval import wrap_module
from odoo.addons.base.models.ir_actions import LoggerProxy

from ...tools import run_preprocessing_script, ExtractNode
from ...exceptions import JsonMissedKey


wrapped_json = wrap_module(json, ['loads', 'dumps'])
wrapped_re = wrap_module(re, ['match', 'fullmatch', 'search', 'sub'])

SCRIPT_PATTERN_ORDER = """# On tab Help you can find the available variables.
# Here write your Python code.


"""

_logger = logging.getLogger(__name__)


class ExternalOrderFieldMapping(models.Model):
    """
    Defines how JSON fields from external orders map to Odoo's sales orders or stock pickings.
    Optionally, a custom Python script can preprocess each field before importing data.

    External Fields:
        - Each mapped 'external_order_field' references a path in the external JSON (e.g. "payment.code").
        - Use 'order' as the root variable to access the entire external order JSON. For example:
          'order.store_name' retrieves the "store_name" attribute from the order JSON.
        - If a field doesn't exist or cannot be located, the mapped Odoo field remains empty
          and a warning is logged instead of raising an exception.
        - Complex data (e.g. {"a": 123}) is automatically serialized into the corresponding
          Odoo field.

    Pre-processing (Optional):
        - A custom Python script can transform the raw 'value' before storing it in Odoo.
        - The following variables are available in the script:
            * integration: the integration record
            * value: the external field's raw value (or None if not found)
            * order: the complete external order JSON
            * logger: Odoo's logger
            * env: the Odoo environment
            * re: the re module
            * json: the json module
        - If no script is provided, the field is imported as-is.

    This model streamlines how external JSON attributes map to Odoo, ensuring greater flexibility
    and making it easier to handle nested or complex data structures in external orders.
    """

    _name = 'external.order.field.mapping'
    _description = 'External Order Field Mapping'

    active = fields.Boolean(
        string='Active',
        default=True,
        help='Indicates if the mapping is active.',
    )

    integration_id = fields.Many2one(
        string='E-Commerce Store',
        comodel_name='sale.integration',
        required=True,
        ondelete='cascade',
    )

    external_order_field = fields.Char(
        string='External Order Field',
        required=True,
        default='order',
    )

    odoo_order_field_id = fields.Many2one(
        comodel_name='ir.model.fields',
        string='Odoo Sales Order Field',
        domain="[('model_id.model', '=', 'sale.order')]",
    )

    odoo_picking_field_id = fields.Many2one(
        comodel_name='ir.model.fields',
        string='Odoo Transfer Field',
        domain="[('model_id.model', '=', 'stock.picking')]",
    )

    script = fields.Text(
        string='Preprocess Script',
        readonly=False,
        default=SCRIPT_PATTERN_ORDER,
        help='Python script to preprocess the value before storing it in Odoo.',
    )

    def get_script(self):
        lines = self.script.splitlines()
        return '\n'.join(line for line in lines if not line.strip().startswith('#')).strip()

    @api.constrains('odoo_order_field_id')
    def _check_unique_order_field(self):
        for rec in self:
            if rec.odoo_order_field_id:
                domain = [
                    ('integration_id', '=', rec.integration_id.id),
                    ('odoo_order_field_id', '=', rec.odoo_order_field_id.id),
                ]
                if self.search_count(domain) > 1:
                    raise ValidationError(_('Sales Order Field must be unique within the same integration.'))

    @api.constrains('odoo_picking_field_id')
    def _check_unique_picking_field(self):
        for rec in self:
            if rec.odoo_picking_field_id:
                domain = [
                    ('integration_id', '=', rec.integration_id.id),
                    ('odoo_picking_field_id', '=', rec.odoo_picking_field_id.id),
                ]
                if self.search_count(domain) > 1:
                    raise ValidationError(_('Transfer Field must be unique within the same integration.'))

    @api.constrains('external_order_field')
    def _check_external_order_field_format(self):
        # Support segments: field names (a-zA-Z0-9_) OR numeric indexes (0,1,2,...), separated by dots
        pattern = re.compile(r'^order(\.(?:[a-zA-Z0-9_]+|\d+))*$')

        for record in self:
            field = (record.external_order_field or '').strip()
            if not field:
                raise ValidationError(_('External Order Field cannot be empty.'))

            if not pattern.fullmatch(field):
                raise ValidationError(_(
                    'External Field can only contain letters, numbers, underscores, dots, '
                    'and numeric index segments.\n\n'
                    'Examples:\n'
                    '- order\n'
                    '- order.id\n'
                    '- order.attribute_id\n'
                    '- order.items.1\n\n'
                    'Rules:\n'
                    '- path starts with "order"\n'
                    '- segments separated by dots\n'
                    '- segment is either a field name (letters/digits/underscore) or an index (digits)'
                ))

    def calculate_order_import_value(self, external_order_data, raise_error: bool = True) -> str:
        """Calculate the value to import into Odoo for this mapping field."""
        self.ensure_one()

        path = (self.external_order_field or '').strip()
        if not path or not path.startswith('order'):
            _logger.warning(f'Invalid Path: Path must start with "order", got "{path}"')
            if raise_error:
                raise UserError(_('Invalid Path: Path must start with "order", got "%s"') % path)
            return None

        # PrestaShop wraps the order data inside an 'order' key
        if 'order' in external_order_data:
            external_order_data = external_order_data['order']

        try:
            value = ExtractNode.extract_raw({'order': external_order_data}, path, '', raise_error=raise_error)

        except JsonMissedKey as e:
            _logger.warning(f'Extraction Warning: Missing key for path "{path}": {e}')
            if raise_error:
                raise UserError(_('Extraction Warning: Missing key for path "%s": %s') % (path, e))
            return None

        except Exception as e:
            _logger.warning(f'Extraction Error: Error extracting value for path "{path}": {e}')
            if raise_error:
                raise UserError(_('Extraction Error: Error extracting value for path "%s": %s') % (path, e))
            return None

        script = self.get_script()
        if not script:
            return value

        ctx = {
            'order': external_order_data,
            'value': value,
            'env': self.env,
            're': wrapped_re,
            'json': wrapped_json,
            'logger': LoggerProxy,
            'integration': self.integration_id,

        }

        return run_preprocessing_script(script, ctx, raise_error=raise_error)

    def action_edit_preprocessing_script(self):
        """
        Open a new window to edit the preprocess script.
        """
        self.ensure_one()

        wizard = self.env['integration.order.field.mapping.editor.wizard'] \
            .create({'mapping_field_id': self.id})

        return wizard.open_form()
