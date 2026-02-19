# See LICENSE file for full copyright and licensing details.
import json
import traceback

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

from ..api.abstract_apiclient import AbsApiClient
from ..exceptions import ApiImportError, NoExternal

# eval to compile generated string python code into binary code, used in `_compile`
unsafe_eval = eval


DRAFT_STATE = 'draft'
CHECKED_STATE = 'checked'
APPROVED_STATE = 'approved'
DONE_STATE = 'done'


def catch_exception(func):
    """
    A decorator to catch exceptions and raise a detailed ValidationError if the
    'integration_catch_exception' context flag is set.

    If the flag is not set, the exception will be re-raised as is.
    """
    def _catch_exception(self, *args, **kw):
        try:
            return func(self, *args, **kw)
        except Exception as ex:
            if self.env.context.get('integration_catch_exception'):
                traceback_details = traceback.format_exc()
                raise ValidationError(_(
                    'An error occurred during the operation: %s\n\n'
                    'Traceback details:\n%s'
                ) % (ex.args[0], traceback_details))

            raise ex
    return _catch_exception


class IntegrationImportProductWizard(models.TransientModel):
    _name = 'integration.import.product.wizard'
    _description = 'Advanced Integration Product Import'

    state = fields.Selection(
        selection=[
            (DRAFT_STATE, 'Draft'),
            (CHECKED_STATE, 'Checked'),
            (APPROVED_STATE, 'Approved'),
            (DONE_STATE, 'Done'),
        ],
        string='State',
        default=DRAFT_STATE,
    )

    operation_mode = fields.Selection(
        selection=[
            ('try_map', 'Try Map External Template (without creating)'),
            ('import', 'Try Map External Template or Create'),
        ],
        string='Operation',
        default='try_map',
    )

    import_images = fields.Boolean(
        string='Import Images',
    )

    external_template_id = fields.Many2one(
        comodel_name='integration.product.template.external',
        string='External Template',
        required=True,
    )

    product_template_id = fields.Many2one(
        comodel_name='product.template',
        string='Product Template',
        compute='_compute_product_template',
    )

    integration_id = fields.Many2one(
        comodel_name='sale.integration',
        related='external_template_id.integration_id',
    )

    line_ids = fields.One2many(
        comodel_name='import.product.line',
        inverse_name='wizard_id',
        string='Mapping Lines',
    )

    internal_line_ids = fields.One2many(
        comodel_name='import.product.line',
        compute='_compute_lines',
        string='Existing Mappings',
    )

    incoming_line_ids = fields.One2many(
        comodel_name='import.product.line',
        compute='_compute_lines',
        string='Incoming Mappings',
    )

    raw_data = fields.Text(
        string='Raw Data',
    )

    @api.depends('external_template_id', 'state')
    def _compute_product_template(self):
        for rec in self:
            rec.product_template_id = rec.external_template_id.odoo_record.id

    @api.depends('line_ids')
    def _compute_lines(self):
        for rec in self:
            rec.internal_line_ids = rec.line_ids.filtered(lambda x: x.type == 'internal')
            rec.incoming_line_ids = rec.line_ids.filtered(lambda x: x.type == 'incoming')

    @property
    def adapter(self):
        return self.integration_id.adapter

    @property
    def operation_try_map(self):
        return self.operation_mode == 'try_map'

    def has_conflicts(self):
        assert self.state == CHECKED_STATE, _('The "%s" state is required.', CHECKED_STATE)

        if set(self.internal_line_ids.mapped('code')).issubset(
            set(self.incoming_line_ids.mapped('code'))
        ):
            return False

        return True

    def set_state(self, name):
        self.state = name

    def save_raw_data(self, data):
        self.raw_data = json.dumps(data, indent=8)

    def read_raw_data(self):
        return json.loads(self.raw_data)

    @catch_exception
    def check(self, external_data=None):
        """
        Method to check the product template and external data, either by mapping or importing.
        This method will also handle incoming lines creation and ensure proper error handling.
        """
        code = self.external_template_id.code

        # Case 1: Try to map
        if self.operation_try_map:
            if not external_data:
                data = self.adapter.get_product_templates([code])

                if not data:
                    raise ApiImportError(_('Product with code "%s" not found in the e-commerce system!') % code)

                external_data = data.get(code, {})

            # Create incoming lines based on external data
            self._create_incoming_lines(external_data)
            raw_data = external_data

        # Case 2: Full product import
        else:
            if not external_data:
                external_data = self.adapter.get_product_for_import(code)

            template_data, variants_data, bom_data, external_images = external_data

            # Create incoming lines based on the raw template and variant data
            self._create_incoming_lines_raw(template_data, variants_data)

            # Helper function to convert external data to dictionary format
            def _convert_to_dict(value):
                if hasattr(value, 'to_dict'):
                    return value.to_dict()  # Convert objects that have `to_dict` method (e.g., from Python, Shopify)
                if not isinstance(value, dict):
                    return {}
                return value

            raw_data = dict(
                TEMPLATE=_convert_to_dict(template_data),
                VARIANTS=[_convert_to_dict(x) for x in variants_data],
                KITS=[_convert_to_dict(x) for x in bom_data],
                IMAGES=[_convert_to_dict(x) for x in external_images],
            )

        if not self.incoming_line_ids:
            raise ApiImportError(_('Error importing external data: No incoming lines created.'))

        self.save_raw_data(raw_data)
        self.set_state(CHECKED_STATE)

        return self.open_form()

    @catch_exception
    def approve(self, force=True):
        if not force:
            if self.has_conflicts():
                raise ValidationError(_(
                    'Mapping conflicts were found between the incoming data and existing records.\n\n'
                    'Manual resolution is required before proceeding with the approval process. '
                    'Please review the following conflicting records:\n\n'
                    'Incoming lines:\n%s\n\nInternal lines:\n%s'
                ) % (
                    self.incoming_line_ids.format_recordset(),
                    self.internal_line_ids.format_recordset(),
                ))

        incoming_codes = self.incoming_line_ids.mapped('code')
        for rec in self.internal_line_ids.filtered(lambda x: x.code not in incoming_codes):
            rec.drop()

        incoming_template_id = self.incoming_line_ids\
            .filtered(lambda x: x.model_name == 'product.template')
        incoming_variant_ids = self.incoming_line_ids\
            .filtered(lambda x: x.model_name == 'product.product')

        origin_parent_id = False
        internal_ids = self.internal_line_ids

        for idx, incoming_line in enumerate(incoming_template_id + incoming_variant_ids, start=1):
            internal_rec = internal_ids.filtered(
                lambda x: x.code == incoming_line.code and x.model_name == incoming_line.model_name
            )

            if idx == 1:
                origin_parent_id = internal_rec.origin_id

            if not internal_rec:
                internal_rec = incoming_line.copy(
                    default={
                        'type': 'internal',
                        'origin_parent_id': origin_parent_id,
                    },
                )
            else:
                internal_rec.write({
                    'name': incoming_line.name,
                    'reference': incoming_line.reference,
                    'barcode': incoming_line.barcode,
                    'attribute_list': incoming_line.attribute_list,
                })

            internal_rec.create_or_update_origin()

        self.set_state(APPROVED_STATE)

        return self.open_form()

    @catch_exception
    def perform(self):
        assert self.state == APPROVED_STATE, _('The "%s" state is required.', APPROVED_STATE)

        if self.operation_try_map:
            self.external_template_id._try_to_map_template_and_variants()

        else:
            self.integration_id\
                .with_context(skip_mapping_validation=True) \
                .import_product(
                    self.external_template_id.id,
                    import_images=self.import_images,
                )

        self._create_internal_lines()

        self.set_state(DONE_STATE)
        return self.open_form()

    def action_open_raw_data(self):
        self.ensure_one()
        return self.open_form()

    def _create_internal_lines(self):
        self.internal_line_ids.unlink()
        external_template_id = self.external_template_id.with_context(default_wizard_id=self.id)
        external_template_id._create_internal_import_line()

        for rec in external_template_id.external_product_variant_ids:
            rec._create_internal_import_line()

        return self.internal_line_ids

    def to_export_format_template(self):
        export = self.product_template_id.to_export_format(self.integration_id)
        self.raw_data = json.dumps(export, indent=8)
        return self.open_form()

    def to_draft(self):
        self.incoming_line_ids.unlink()
        self._create_internal_lines()
        self.set_state(DRAFT_STATE)

        self.raw_data = False
        return self.open_form()

    def _create_incoming_lines_raw(self, template_data, variants_data):
        self.incoming_line_ids.unlink()
        vals = dict(
            wizard_id=self.id,
            name=self.external_template_id.name,
        )

        main_line = self._create_template_incoming_line(
            self.integration_id.id,
            self.external_template_id.code,
            (template_data, {})
        )
        main_line.write(vals)

        if not variants_data:
            main_line._create_default_variant_line()

        for variant_data in variants_data:
            line = self._create_variant_incoming_line(
                self.integration_id.id,
                self.external_template_id.code,
                (template_data, variant_data),
            )
            line.write(vals)

        return self.incoming_line_ids

    def _create_incoming_lines(self, external_data):
        self.incoming_line_ids.unlink()
        ProductLine = self.line_ids.browse()

        main_line = ProductLine.create({
            'name': external_data['name'],
            'code': external_data['id'],
            'reference': external_data['external_reference'],
            'barcode': external_data['barcode'],
            'model_name': 'product.template',
            'wizard_id': self.id,
            'type': 'incoming',
        })

        for variant_data in external_data['variants']:
            ProductLine.create({
                'name': variant_data['name'],
                'code': variant_data['id'],
                'reference': variant_data['external_reference'],
                'barcode': variant_data['barcode'],
                'attribute_list': str(variant_data['attribute_value_ids']),
                'model_name': 'product.product',
                'wizard_id': self.id,
                'type': 'incoming',
            })

        if not external_data['variants']:
            main_line._create_default_variant_line()

        return self.incoming_line_ids

    def _create_template_incoming_line(
        self,
        integration_id: int,
        external_template_code: str,
        data: tuple,
    ) -> models.Model:
        integration = self.env['sale.integration'].browse(integration_id)

        reference_mapping = integration.template_reference_id \
            ._get_mapping_for_integration(integration_id)

        if reference_mapping:
            reference_dict = reference_mapping.calculate_import_value(*data)
            reference = reference_dict.popitem()[1]
        else:
            reference = None

        barcode_mapping = integration.template_barcode_id \
            ._get_mapping_for_integration(integration_id)

        if barcode_mapping:
            barcode_dict = barcode_mapping.calculate_import_value(*data)
            barcode = barcode_dict.popitem()[1]
        else:
            barcode = None

        vals = {
            'code': external_template_code,
            'model_name': 'product.template',
            'type': 'incoming',
            'reference': reference,
            'barcode': barcode,
        }

        return self.env['import.product.line'].create(vals)

    def _create_variant_incoming_line(
        self,
        integration_id: int,
        external_template_code: str,
        data: tuple,
    ) -> models.Model:
        integration = self.env['sale.integration'].browse(integration_id)

        reference_mapping = integration.product_reference_id \
            ._get_mapping_for_integration(integration_id)

        if reference_mapping:
            reference_dict = reference_mapping.calculate_import_value(*data)
            reference = reference_dict.popitem()[1]
        else:
            reference = None

        barcode_mapping = integration.product_barcode_id \
            ._get_mapping_for_integration(integration_id)

        if barcode_mapping:
            barcode_dict = barcode_mapping.calculate_import_value(*data)
            barcode = barcode_dict.popitem()[1]
        else:
            barcode = None

        __, variant_data = data

        vals = {
            'model_name': 'product.product',
            'type': 'incoming',
            'reference': reference,
            'barcode': barcode,
            'attribute_list': str(variant_data['_attribute_value_ids']),
            'code': AbsApiClient._build_product_external_code(
                external_template_code,
                variant_data['id'],
            ),
        }

        return self.env['import.product.line'].create(vals)

    def open_form(self):
        # self.read()
        return {
            'type': 'ir.actions.act_window',
            'name': (
                f'({self.id}) {self.integration_id.name}: {self._description} [{self.external_template_id.id}]'
            ),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('integration.integration_import_product_wizard_form').id,
            'target': 'new',
            'context': self.env.context,
        }


class ImportProductLine(models.TransientModel):
    _name = 'import.product.line'
    _description = 'Import Product Line'

    origin_id = fields.Integer(
        string='Origin ID'
    )

    origin_parent_id = fields.Integer(
        string='Origin Parent ID'
    )

    name = fields.Char(
        string='Name',
    )

    code = fields.Char(
        string='Code',
    )

    reference = fields.Char(
        string='Reference',
    )

    barcode = fields.Char(
        string='Barcode',
    )

    attribute_list = fields.Char(
        string='Attributes',
        default='[]',
    )

    mapping_id = fields.Integer(
        string='Mapping ID',
    )

    odoo_id = fields.Integer(
        string='Odoo ID',
    )

    model_name = fields.Selection(
        selection=[
            ('product.product', 'Variant'),
            ('product.template', 'Template'),
        ],
        string='Model',
    )

    type = fields.Selection(
        selection=[
            ('internal', 'Internal'),
            ('incoming', 'Incoming'),
        ],
        string='Type',
    )

    wizard_id = fields.Many2one(
        comodel_name='integration.import.product.wizard',
        string='Wizard',
        ondelete='cascade',
    )

    state = fields.Selection(
        related='wizard_id.state',
    )

    integration_id = fields.Many2one(
        comodel_name='sale.integration',
        related='wizard_id.integration_id',
    )

    @property
    def model(self):
        return self.env[f'integration.{self.model_name}.external']

    @property
    def record(self):
        return self.model.browse(self.origin_id)

    @property
    def is_variant(self):
        return self.model_name == 'product.product'

    def drop(self):
        wizard = self.wizard_id

        self.record.unlink()
        self.unlink()

        return wizard.open_form()

    def create_or_update_origin(self):
        vals = self._prepare_origin_vals()

        if self.origin_id:
            self.record.write(vals)
        else:
            origin = self.model.create_or_update(vals)
            self.origin_id = origin.id

        self.record.create_or_update_mapping()

        return self.record

    def format_recordset(self):
        return str(
            self.mapped(
                lambda x: (f'<id={x.id}>', x.code, x.reference, x.barcode)
            )
        )

    def _prepare_origin_vals(self):
        vals = dict(
            code=self.code,
            name=self.name,
            external_reference=self.reference,
            external_barcode=self.barcode,
            integration_id=self.integration_id.id,
        )

        if self.is_variant:
            vals.update(
                external_product_template_id=self.origin_parent_id,
                external_attribute_value_ids=self._parse_attributes(),
            )

        return vals

    def _parse_attributes(self):
        AttributeValue = self.env['integration.product.attribute.value.external']
        value_ids = AttributeValue.browse()
        integration = self.integration_id

        for code in unsafe_eval(self.attribute_list):
            record = AttributeValue.search([
                ('code', '=', code),
                ('integration_id', '=', integration.id),
            ])

            if not record:
                raise NoExternal(
                    _(
                        '\nCannot find external attribute value for code "%s".\n'
                        'Please ensure that all relevant attribute values are imported from the '
                        'e-commerce system for the integration "%s" (ID: %s).'
                    ) % (code, integration.name, integration.id),
                    model_name=AttributeValue._name,
                    code=code,
                    integration=integration,
                )

            value_ids |= record

        return [(6, 0, value_ids.ids)]

    def _create_default_variant_line(self):
        return self.create({
            'name': self.name,
            'code': f'{self.code}-0',
            'reference': self.reference,
            'barcode': self.barcode,
            'model_name': 'product.product',
            'wizard_id': self.wizard_id.id,
            'type': 'incoming',
        })


class ImportProductField(models.TransientModel):
    _name = 'integration.import.product.field'
    _description = 'Import Product Field'

    mapping_ecommerce_field_id = fields.Many2one(
        comodel_name='product.ecommerce.field.mapping',
        string='Mapping Ecommerce Field',
    )

    name = fields.Char(
        related='mapping_ecommerce_field_id.name',
    )

    import_script = fields.Text(
        related='mapping_ecommerce_field_id.import_script',
    )

    memo_in = fields.Char(
        string='Memo In',
    )

    export_script = fields.Text(
        related='mapping_ecommerce_field_id.export_script',
    )

    memo_out = fields.Char(
        string='Memo Out',
    )

    import_wizard_id = fields.Many2one(
        comodel_name='integration.import.product.wizard',
        string='Import Wizard',
        ondelete='cascade',
    )

    state = fields.Selection(
        related='import_wizard_id.state',
    )

    operation_mode = fields.Selection(
        related='import_wizard_id.operation_mode',
    )

    product_template_id = fields.Many2one(
        comodel_name='product.template',
        related='import_wizard_id.product_template_id',
    )
