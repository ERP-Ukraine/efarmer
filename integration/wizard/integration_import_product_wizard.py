# See LICENSE file for full copyright and licensing details.

import traceback
from io import StringIO

from odoo import models, fields, api, _
from odoo.tools import unsafe_eval
from odoo.exceptions import ValidationError

from ..exceptions import ApiImportError, NoExternal


DRAFT_STATE = 'draft'
CHECKED_STATE = 'checked'
APPROVED_STATE = 'approved'
DONE_STATE = 'done'


def catch_exception(func):
    def _catch_exception(self, *args, **kw):
        try:
            return func(self, *args, **kw)
        except Exception as ex:
            if self._context.get('integration_catch_exception'):
                buff = StringIO()
                traceback.print_exc(file=buff)
                raise ValidationError(f'{ex.args[0]} -->\n\n{buff.getvalue()}')
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

    external_template_id = fields.Many2one(
        comodel_name='integration.product.template.external',
        string='External Template',
        required=True,
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
        assert self.state == CHECKED_STATE, _(f'The "{CHECKED_STATE}" state is required.')

        if set(self.internal_line_ids.mapped('code')).issubset(
            set(self.incoming_line_ids.mapped('code'))
        ):
            return False

        return True

    def set_state(self, name):
        self.state = name

    @catch_exception
    def check(self, external_data=None):
        code = self.external_template_id.code

        if self.operation_try_map:
            if not external_data:
                data = self.adapter.get_product_templates([code])
                external_data = data.get(code, {})
            self._create_incoming_lines(external_data)
        else:
            if not external_data:
                external_data = self.adapter.get_product_for_import(code)
            self._create_incoming_lines_raw(external_data[0], external_data[1])

        if not self.incoming_line_ids:
            raise ApiImportError(_('External data import error!'))

        self.set_state(CHECKED_STATE)

        return self.open_form()

    @catch_exception
    def approve(self, force=True):
        if not force:
            if self.has_conflicts():
                raise ValidationError(
                    _('Mapping conflicts found. Make manual import.\n\n%s --> %s')
                    % (
                        self.incoming_line_ids.format_recordset(),
                        self.internal_line_ids.format_recordset(),
                    )
                )

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
        assert self.state == APPROVED_STATE, _(f'The "{APPROVED_STATE}" state is required.')

        if self.operation_try_map:
            self.external_template_id._try_to_map_template_and_variants()

        else:
            self.integration_id.with_context(skip_mapping_validation=True)\
                .import_product(self.external_template_id.id, import_images=True)

        self._create_internal_lines()

        self.set_state(DONE_STATE)
        return self.open_form()

    def _create_internal_lines(self):
        self.internal_line_ids.unlink()
        external_template_id = self.external_template_id.with_context(default_wizard_id=self.id)
        external_template_id._create_internal_import_line()

        for rec in external_template_id.external_product_variant_ids:
            rec._create_internal_import_line()

        return self.internal_line_ids

    def to_draft(self):
        self.incoming_line_ids.unlink()
        self._create_internal_lines()
        self.set_state(DRAFT_STATE)
        return self.open_form()

    def _create_incoming_lines_raw(self, template, variants_data):
        self.incoming_line_ids.unlink()
        self_ = self.with_context(
            default_wizard_id=self.id,
            default_name=self.external_template_id.name,
        )

        t_converter = self_.integration_id\
            .init_receive_field_converter(self_.env['product.template'], template)

        main_line = t_converter._create_product_incoming_line()

        if not variants_data:
            main_line._create_default_variant_line()

        for data in variants_data:
            converter = self_.integration_id\
                .init_receive_field_converter(self_.env['product.product'], data)
            converter._create_product_incoming_line()

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

    def open_form(self):
        return {
            'type': 'ir.actions.act_window',
            'name': (
                f'{self.integration_id.name}: {self._description} [{self.external_template_id.id}]'
            ),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('integration.integration_import_import_product_wizard_form').id,
            'target': 'new',
            'context': self._context,
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
                    _('Cannot find external record'), AttributeValue._name, code, integration
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
