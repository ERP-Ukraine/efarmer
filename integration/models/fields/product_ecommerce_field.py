# See LICENSE file for full copyright and licensing details.

import logging
from datetime import datetime

from odoo import api, models, fields, _
from odoo.exceptions import UserError, ValidationError

from ..sale_integration import DATETIME_FORMAT
from ...api.abstract_apiclient import AbsApiClient
from ...tools import IS_TRUE, IS_FALSE, run_preprocessing_script, ExtractNode, is_translated_value


_logger = logging.getLogger(__name__)

BOOLEAN_FIELD = 'boolean'
INTEGER_FIELD = 'integer'
FLOAT_FIELDS = ['float', 'monetary']
TEXT_FIELDS = ['char', 'text', 'html']

PRODUCT_BUSINESS_MODELS = [
    'product.product',
    'product.template',
]

SCRIPT_PATTERN = """# On tab Help you can find the available variables.
# Here write your Python code. Note that your script must to have a "value" variable,
# which will be returned by "safe_eval" function instead of direct "return" notation.


"""


def _convert_to_import_type(value, import_field_type: str):
    """
    Convert a value from external e-commerce format to Odoo field type.

    :param value: Raw value from external API
    :param field_type: Target Odoo field type (boolean, integer, float, monetary, char, text, html)
    :return: Converted value matching the target field type
    """
    if import_field_type == BOOLEAN_FIELD:
        if value in (IS_TRUE, IS_FALSE):
            value = int(value)
        return bool(value)

    if import_field_type == INTEGER_FIELD:
        return int(value) if value else 0

    if import_field_type in FLOAT_FIELDS:
        return float(value) if value else 0.0

    if import_field_type in TEXT_FIELDS:
        return str(value) if value else False

    return value


def _convert_to_export_type(value, export_field_type: str):
    """
    Convert a value from Odoo format to external e-commerce API type.

    :param value: Value from Odoo field
    :param field_type: Target API type (boolean, integer, float, string)
    :return: Converted value matching the target API type
    """
    if export_field_type == 'boolean':
        return bool(value)

    if export_field_type == 'integer':
        return int(value) if value else 0

    if export_field_type == 'float':
        return round(float(value), 6) if value else 0.0

    if export_field_type == 'string':
        return str(value) if value else ''

    return value


class ProductEcommerceField(models.Model):
    _name = 'product.ecommerce.field'
    _description = 'Ecommerce field depending on integration type'

    name = fields.Char(
        string='Field Name',
        required=True,
        help='Here we have field name like it is displayed on user interface'
    )

    technical_name = fields.Char(
        string='API Field Name',
        required=True,
        help='Here we have Field like it is referred to in the API',
    )

    type_api = fields.Selection(
        selection=[
            ('no_api', 'Not Use API'),
        ],
        string='Connector Type',
        required=True,
        ondelete={
            'no_api': 'cascade',
        },
        help='Every field exists only together with it\'s e-commerce system. '
             'So here we define which e-commerce system this field is related to. '
             'This should be updated for every new integration.',
    )

    default_for_update = fields.Boolean(
        string='Export (Odoo → Shop) Enabled',
        help='By default fields that are available in the fields mapping will be ALL used to '
             'create new product record on external e-commerce system. But after record is '
             'created, we do not want to mess up and override changes that are done for '
             'that field on external system. Hence we can specify here if that field will '
             'be default also for Updating. Value from here will be copied to the mapping '
             'on Sales Integration creation.',
    )

    default_for_import = fields.Boolean(
        string='Import (Shop → Odoo) Enabled',
        default=False,
        help='By default fields that are available in the fields mapping will be ALL used to '
             'create new product Odoo. But after record is '
             'created, we do not want to mess up and override changes that are done for '
             'that field in Odoo. Hence we can specify here if that field will '
             'be default also for Import in Odoo. Value from here will be copied to the mapping '
             'on Sales Integration creation.',
    )

    is_default = fields.Boolean(
        string='Default',
        default=False,
        help='Technical field',
    )

    auto_create_mapping = fields.Boolean(
        string='Auto-Add to New Stores',
        default=False,
        help='When new Integration of API type is created, field mapping will '
             'be automatically pre-created based on this checkbox. So user do not '
             'need to create mapping manually',
    )

    odoo_model_id = fields.Many2one(
        string='Odoo Model',
        comodel_name='ir.model',
        required=True,
        ondelete='cascade',
        domain=[('model', 'in', PRODUCT_BUSINESS_MODELS)],
        help='Here we select model which will be used to retrieve data from'
    )

    odoo_model_name = fields.Char(
        related='odoo_model_id.model',
        store=True,
    )

    odoo_field_id = fields.Many2one(
        string='Odoo Field',
        comodel_name='ir.model.fields',
        ondelete='cascade',
        domain='[("model_id", "=", odoo_model_id)]',
        help='For simple fields you can select here field name from defined model to retrieve information from',
    )

    odoo_field_name = fields.Char(
        string='Odoo Field Name',
        related='odoo_field_id.name',
        store=True,
    )

    trackable_fields_ids = fields.Many2many(
        string='Tracked Fields',
        comodel_name='ir.model.fields',
        ondelete='cascade',
        domain='[("model_id", "=", odoo_model_id)]',
        help='Here we can select fields that will run export process when they are updated.',
    )

    is_private = fields.Boolean(
        string='Private',
        help='Technical property for developers needs',
    )

    mapping_ids = fields.One2many(
        comodel_name='product.ecommerce.field.mapping',
        inverse_name='ecommerce_field_id',
        string='Mappings',
    )

    integration_id = fields.Many2one(
        comodel_name='sale.integration',
        string='Integration',
        store=False,
    )

    mapping_id = fields.Many2one(
        comodel_name='product.ecommerce.field.mapping',
        string='Mapping',
        domain='[("id", "in", mapping_ids)]',
        store=False,
    )

    external_template_id = fields.Many2one(
        comodel_name='integration.product.template.external',
        string='External Template',
        store=False,
        search=True,  # To avoid UserWarning: Field should be searchable (from Field.resolve_depends)
    )

    external_variant_id = fields.Many2one(
        comodel_name='integration.product.product.external',
        string='External Variant',
        store=False,
    )

    external_variant_ids = fields.One2many(
        comodel_name='integration.product.product.external',
        related='external_template_id.external_product_variant_ids',
    )

    template_id = fields.Many2one(
        comodel_name='product.template',
        string='Template',
        store=False,
        search=True,  # To avoid UserWarning: Field should be searchable (from Field.resolve_depends)
    )

    variant_id = fields.Many2one(
        comodel_name='product.product',
        string='Variant',
        store=False,
    )

    variant_ids = fields.One2many(
        comodel_name='product.product',
        related='template_id.product_variant_ids',
    )

    export_field_type = fields.Selection(
        selection=[
            ('boolean', 'Boolean'),
            ('integer', 'Integer'),
            ('float', 'Float'),
            ('string', 'String'),
        ],
        string='Export Output Type',
    )

    import_script = fields.Text(
        string='Preprocess Script In',
        readonly=False,
        default=SCRIPT_PATTERN,
        help='Python script to preprocess the value before storing it in Odoo.',
    )

    export_script = fields.Text(
        string='Preprocess Script Out',
        readonly=False,
        default=SCRIPT_PATTERN,
        help='Python script to preprocess the value before storing it in Odoo.',
    )

    is_translatable_field = fields.Boolean(
        string='Multi-Language',
        readonly=True,
    )

    is_template_field = fields.Boolean(
        string='Is Template Field',
        compute='_compute_is_product_field',
    )

    is_variant_field = fields.Boolean(
        string='Is Variant Field',
        compute='_compute_is_product_field',
    )

    is_scriptable_field = fields.Boolean(
        string='Uses Script',
        compute='_compute_is_scriptable_field',
        store=True,
    )

    @api.depends('odoo_model_id')
    def _compute_is_product_field(self):
        for rec in self:
            rec.is_template_field = rec.odoo_model_name == 'product.template'
            rec.is_variant_field = rec.odoo_model_name == 'product.product'

    @api.depends('import_script', 'export_script')
    def _compute_is_scriptable_field(self):
        for rec in self:
            rec.is_scriptable_field = bool(rec.import_script_clean) or bool(rec.export_script_clean)

    @property
    def import_field_type(self):
        """
        Get the Odoo field type for import conversion.

        :return: Odoo field type string (e.g., 'char', 'integer', 'boolean')
        """
        self.ensure_one()
        return self.sudo().odoo_field_id.ttype

    @property
    def import_script_clean(self):
        """
        Get the import script with comment lines removed.

        :return: Cleaned script string ready for execution
        """
        lines = self.import_script.splitlines()
        return '\n'.join(line for line in lines if not line.strip().startswith('#')).strip()

    @property
    def export_script_clean(self):
        """
        Get the export script with comment lines removed.

        :return: Cleaned script string ready for execution
        """
        lines = self.export_script.splitlines()
        return '\n'.join(line for line in lines if not line.strip().startswith('#')).strip()

    @api.onchange('odoo_field_id')
    def _onchange_odoo_field_id(self):
        """
        On change of odoo_field_id automatically set trackable_fields_ids
        """
        self.trackable_fields_ids = self.odoo_field_id

    @api.model_create_multi
    def create(self, vals_list):
        """
        Override create method to ensure that if odoo_field_id is provided,
        the trackable_fields_ids is automatically set to include that field.
        Also ensure that script fields have default pattern if not provided.
        """
        for vals in vals_list:
            if 'trackable_fields_ids' not in vals and vals.get('odoo_field_id'):
                vals['trackable_fields_ids'] = [(6, 0, [vals['odoo_field_id']])]

            # Set default script pattern if not provided or empty
            if 'import_script' not in vals or not vals.get('import_script'):
                vals['import_script'] = SCRIPT_PATTERN
            if 'export_script' not in vals or not vals.get('export_script'):
                vals['export_script'] = SCRIPT_PATTERN

        return super(ProductEcommerceField, self).create(vals_list)

    def make_copy(self):
        """
        Create a copy of the field configuration with default scripts.
        """
        self.ensure_one()

        kw = {}
        if not self.import_script:
            kw['import_script'] = SCRIPT_PATTERN
        if not self.export_script:
            kw['export_script'] = SCRIPT_PATTERN

        return self.copy(
            default={
                'is_default': False,
                'name': self.name + ' (Copy)',
                **kw,
            }
        )

    def _get_mapping_for_integration(self, integration_id: int, mark_active: bool = True):
        """
        Get existing mapping for the given integration.

        :param integration_id: ID of the sale.integration record
        :param mark_active: If True, reactivate inactive mapping if found
        :return: product.ecommerce.field.mapping record or empty recordset
        :raises UserError: If multiple active mappings found for same integration
        """
        assert len(self) <= 1, _('Recordsets not allowed')

        mapping = self.mapping_ids.filtered(lambda x: x.integration_id.id == integration_id)

        if len(mapping) > 1:
            raise UserError(
                _(
                    'Multiple mappings found for the e-commerce field "%s" in the integration "%s". '
                    'Please ensure that each e-commerce field has only one active mapping for this integration.'
                ) % (self.name, self.env['sale.integration'].browse(integration_id).name)
            )

        if not mapping:
            mapping = self.with_context(active_test=False).mapping_ids\
                .filtered(lambda x: x.integration_id.id == integration_id)[:1]

            if mark_active:
                mapping.mark_active()

        return mapping

    def mark_mapping_inactive(self, integration_id: int):
        """
        Mark the mapping for the given integration as inactive.

        :param integration_id: ID of the sale.integration record
        :return: Result of mark_inactive() call
        """
        assert len(self) <= 1, _('Recordsets not allowed')
        mapping = self.mapping_ids.filtered(lambda x: x.integration_id.id == integration_id)

        return mapping.mark_inactive()

    def _ensure_mapping(self, integration_id: int, mark_active: bool = True):
        """
        Ensure a mapping exists for the given integration, creating one if necessary.

        :param integration_id: ID of the sale.integration record
        :param mark_active: If True, ensure the mapping is active
        :return: product.ecommerce.field.mapping record or True if private field
        """
        self.ensure_one()

        if self.is_private:
            return True

        mapping = self._get_mapping_for_integration(integration_id, mark_active=mark_active)

        if not mapping:
            kw = {'active': True} if mark_active else {}
            mapping = self._create_mapping(integration_id, **kw)

        return mapping

    def _create_mapping(self, integration_id: int, **kwargs):
        """
        Create a new mapping for the given integration.

        :param integration_id: ID of the sale.integration record
        :param kwargs: Additional values to set on the mapping
        :return: Created product.ecommerce.field.mapping record
        """
        return self.env['product.ecommerce.field.mapping'].create({
            'ecommerce_field_id': self.id,
            'integration_id': integration_id,
            'active': self.auto_create_mapping,
            'export_enabled': self.default_for_update,
            'import_enabled': self.default_for_import,
            **kwargs,
        })

    def action_open_test_wizard(self):
        """
        Open the test wizard for this field definition.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Test Field Mapping'),
            'res_model': 'product.ecommerce.field.test.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_ecommerce_field_id': self.id,
            },
        }

    def action_unlink(self):
        return self.unlink()

    def action_open_form(self, **context):
        """
        Open the field configuration form in a modal window.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'view_id': self.env.ref('integration.product_ecommerce_field_view_form').id,
            'context': context,
        }

    def get_odoo_record(self, odoo_id: int = None):
        """
        Get an Odoo record for the configured model.

        :param odoo_id: Optional record ID to browse
        :return: Empty recordset or browsed record for the configured model
        """
        self.ensure_one()
        record = self.env[self.odoo_model_name]

        if odoo_id:
            record = record.browse(odoo_id)

        return record

    def get_api_field_name(self, field_name_only: bool = False) -> str:
        """
        Get the API field name for external e-commerce system.

        :param field_name_only: If True, return only the last part of dotted path
        :return: API field name string
        """
        value = self.technical_name

        if field_name_only:
            value = value.split('.')[-1]

        return value

    def get_odoo_field_name(self, raise_if_not_found: bool = False) -> str:
        """
        Get the Odoo field name for this mapping.

        :param raise_if_not_found: If True, raise error when field is not configured
        :return: Odoo field name string or empty string
        :raises UserError: If raise_if_not_found=True and no field configured
        """
        field = self.odoo_field_name

        if raise_if_not_found and not field:
            raise UserError(_('Field "%s" has no related Odoo field.') % self.name)

        return field

    def _build_script_context(self, **kw) -> dict:
        """
        Build base context dictionary for script execution.

        :param kw: Additional context variables to include
        :return: Dictionary with common variables for safe_eval
        """
        return {
            'field': self,
            'env': self.env,
            'datetime': datetime,
            'UserError': UserError,
            'ValidationError': ValidationError,
            'DATETIME_FORMAT': DATETIME_FORMAT,
            **kw,
        }

    # ==================== Import Flow ====================
    # Flow: calculate_import_value() → _build_import_field_dict() → _extract_import_value()
    #                                                             → convert_to_import_type()

    def calculate_import_value(self, integration_id: int, data: tuple, odoo_id: int = False):
        """
        Entry point for import flow: converts external e-commerce data to Odoo field value.

        Flow:
            calculate_import_value()
            ├── [if script] → run preprocessing script with _build_import_script_context()
            └── [no script] → _build_import_field_dict()
                                └── _extract_import_value()
                                      └── convert_to_import_type()

        :param integration_id: ID of the sale.integration record
        :param data: Tuple of (template_data, variant_data) from external API
        :param odoo_id: Optional Odoo record ID (product.template or product.product)
        :return: Dict with {odoo_field_name: converted_value} or script result
        """
        _logger.info('%s: calculate_import_value: %s', integration_id, self.technical_name)
        self.ensure_one()

        _logger.info(
            '[%s] Integration preprocessing IN: Processing script for %s (id=%s)',
            integration_id, self.name, self.id
        )

        script = self.import_script_clean

        if not script:
            return self._build_import_field_dict(integration_id, data)

        ctx = self._build_import_script_context(integration_id, data, odoo_id)

        return run_preprocessing_script(script, ctx, raise_error=True)

    def _build_import_field_dict(self, integration_id: int, data: tuple):
        """
        Build dictionary mapping Odoo field name to converted import value.

        :param integration_id: ID of the sale.integration record
        :param data: Tuple of (template_data, variant_data) from external API
        :return: Dict with {odoo_field_name: converted_value}
        """
        _logger.info('%s: _build_import_field_dict: %s', integration_id, self.technical_name)
        self.ensure_one()

        value = self._extract_import_value(integration_id, data)

        value_ = self.env['integration.res.lang.mapping'] \
            .convert_external_translations(integration_id, value)

        odoo_name = self.get_odoo_field_name(raise_if_not_found=True)

        return {odoo_name: value_}

    def _extract_import_value(self, integration_id: int, data: tuple):
        """
        Extract and convert field value from external API data.

        :param integration_id: ID of the sale.integration record
        :param data: Tuple of (template_data, variant_data) from external API
        :return: Converted value ready for Odoo field
        """
        template_data, variant_data = data

        if self.is_template_field:
            source_data = template_data
        else:
            source_data = variant_data

        api_name = self.get_api_field_name()
        value = ExtractNode.extract_raw(source_data, api_name, '', raise_error=False)

        return self.convert_to_import_type(integration_id, value)

    def _build_import_script_context(self, integration_id: int, data: tuple, odoo_id: int) -> dict:
        """
        Build context dictionary for import preprocessing script execution.

        :param integration_id: ID of the sale.integration record
        :param data: Tuple of (template_data, variant_data) from external API
        :param odoo_id: Odoo record ID for the target product
        :return: Dictionary with variables available during safe_eval execution
        """
        self.ensure_one()
        template_data, variant_data = data

        odoo_record = self.get_odoo_record(odoo_id)

        if odoo_record.is_template:
            code = str(template_data['id'])
            template = odoo_record
            variant = self.env['product.product']
        else:
            code = AbsApiClient._build_product_external_code(
                template_data['id'],
                variant_data['id'] if variant_data else None
            )
            template = odoo_record.product_tmpl_id
            variant = odoo_record

        return self._build_script_context(
            template=template,
            variant=variant,
            external_data=data,
            external_code=code,
            integration=self.env['sale.integration'].browse(integration_id),
            VARIANTS_COUNT=template_data['_variants_count'],
            FIRST_TIME_IMPORT=bool(self.env.context.get('integration_first_time_import')),
        )

    def convert_to_import_type(self, integration_id: int, value):
        """
        Convert external value to match the target Odoo field type.

        Handles both simple values and translated value structures.

        :param integration_id: ID of the sale.integration record
        :param value: Raw value from external API (may be translated structure)
        :return: Value converted to match Odoo field type
        """
        self.ensure_one()

        import_field_type = self.import_field_type

        if not import_field_type:
            return value

        if is_translated_value(value):
            if isinstance(value['language'], dict):
                value_ = value['language']['value']
                value['language']['value'] = _convert_to_import_type(value_, import_field_type)
            elif isinstance(value['language'], list):
                for item in value['language']:
                    value_ = item['value']
                    item['value'] = _convert_to_import_type(value_, import_field_type)

            return value

        return _convert_to_import_type(value, import_field_type)

    # ==================== Export Flow ====================
    # Flow: calculate_export_value() → _build_export_field_dict() → _prepare_export_value()
    #                                                             → convert_to_export_type()

    def calculate_export_value(self, integration_id: int, odoo_id: int):
        """
        Entry point for export flow: converts Odoo field value to external e-commerce format.

        Flow:
            calculate_export_value()
            ├── [if script] → run preprocessing script with _build_export_script_context()
            └── [no script] → _build_export_field_dict()
                                └── _prepare_export_value()
                                      └── convert_to_export_type()

        :param integration_id: ID of the sale.integration record
        :param odoo_id: Odoo record ID (product.template or product.product)
        :return: Dict with {api_field_name: converted_value} or script result
        """
        _logger.info('Integration %s: calculate_export_value: %s', integration_id, self.technical_name)
        self.ensure_one()

        script = self.export_script_clean

        if not script:
            return self._build_export_field_dict(integration_id, odoo_id)

        ctx = self._build_export_script_context(integration_id, odoo_id)

        return run_preprocessing_script(script, ctx, raise_error=True)

    def _build_export_field_dict(self, integration_id: int, odoo_id: int):
        """
        Build dictionary mapping API field name to converted export value.

        :param integration_id: ID of the sale.integration record
        :param odoo_id: Odoo record ID (product.template or product.product)
        :return: Dict with {api_field_name: converted_value}
        """
        _logger.info('Integration %s: _build_export_field_dict: %s', integration_id, self.technical_name)
        self.ensure_one()

        value = self._prepare_export_value(integration_id, odoo_id)
        api_name = self.get_api_field_name()

        return {api_name: value}

    def _prepare_export_value(self, integration_id: int, odoo_id: int):
        """
        Read and convert Odoo field value for export to external system.

        :param integration_id: ID of the sale.integration record
        :param odoo_id: Odoo record ID (product.template or product.product)
        :return: Converted value ready for external API
        """
        odoo_name = self.get_odoo_field_name()
        odoo_record = self.get_odoo_record(odoo_id)

        value = odoo_record.convert_field_value_to_external(
            integration_id,
            odoo_name,
            translate=self.is_translatable_field,
        )

        return self.convert_to_export_type(integration_id, value)

    def _build_export_script_context(self, integration_id: int, odoo_id: int) -> dict:
        """
        Build context dictionary for export preprocessing script execution.

        :param integration_id: ID of the sale.integration record
        :param odoo_id: Odoo record ID for the source product
        :return: Dictionary with variables available during safe_eval execution
        """
        self.ensure_one()

        odoo_record = self.get_odoo_record(odoo_id)

        if self.is_template_field:
            template_record = odoo_record
            variant_record = self.env['product.product']
        else:
            template_record = odoo_record.product_tmpl_id
            variant_record = odoo_record

        code = odoo_record.get_external_code(integration_id) or ''
        variants = template_record.prepare_integration_variants(integration_id)

        return self._build_script_context(
            template=template_record,
            variant=variant_record,
            integration=self.env['sale.integration'].browse(integration_id),
            EXTERNAL_CODE=code,
            VARIANTS_COUNT=len(variants),
            FORCE_PRODUCT_EXPORT=bool(self.env.context.get('integration_force_product_export')),
        )

    def convert_to_export_type(self, integration_id: int, value):
        """
        Convert Odoo value to match the target external API type.

        Handles both simple values and translated value structures.

        :param integration_id: ID of the sale.integration record
        :param value: Value from Odoo field (may be translated structure)
        :return: Value converted to match external API type
        """
        self.ensure_one()

        export_field_type = self.export_field_type

        if not export_field_type:
            return value

        if is_translated_value(value):
            for k, v in value['language'].items():
                value['language'][k] = _convert_to_export_type(v, export_field_type)

            return value

        return _convert_to_export_type(value, export_field_type)
