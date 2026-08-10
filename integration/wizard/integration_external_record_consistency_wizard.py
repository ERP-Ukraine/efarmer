# See LICENSE file for full copyright and licensing details.

from collections.abc import Iterable, Mapping

from odoo import api, fields, models, _
from odoo.exceptions import UserError


STATUS_MISSING = 'missing'
STATUS_UNMAPPED = 'unmapped'
STATUS_VARIANT_MISMATCH = 'variant_mismatch'
STATUS_OK = 'ok'
STATUS_DELETED = 'deleted'

# Status order defines display priority in the wizard lines.
LINE_STATUS_SELECTION = [
    (STATUS_DELETED, 'Deleted'),
    (STATUS_MISSING, 'Missing in Store'),
    (STATUS_UNMAPPED, 'Unmapped'),
    (STATUS_VARIANT_MISMATCH, 'Variants Mismatch'),
    (STATUS_OK, 'OK'),
]

FILTER_STATUS_ALL = 'all'
FILTER_STATUS_SELECTION = [
    (FILTER_STATUS_ALL, 'All'),
    *LINE_STATUS_SELECTION,
]

STATUS_PRIORITY = {
    status: index
    for index, (status, __) in enumerate(LINE_STATUS_SELECTION)
}

VARIANT_MISMATCH_EXTERNAL_MODELS = {
    'integration.product.template.external',
}


class IntegrationExternalRecordConsistencyWizard(models.TransientModel):
    _name = 'integration.external.record.consistency.wizard'
    _description = 'External Records Consistency Check'

    integration_id = fields.Many2one(
        comodel_name='sale.integration',
        string='E-Commerce Store',
        required=True,
        default=lambda self: self.env.context.get('default_integration_id'),
    )
    integration_type = fields.Selection(related='integration_id.type_api', readonly=True)
    entity_id = fields.Many2one(
        comodel_name='integration.import.entity',
        string='Entity',
        required=True,
        domain=(
            '["&", '
            '("consistency_method_name", "!=", False), '
            '"|", ("integration_type", "=", False), ("integration_type", "=", integration_type)]'
        ),
        default=lambda self: self.env.context.get('default_entity_id'),
    )
    line_ids = fields.One2many(
        'integration.external.record.consistency.wizard.line', 'wizard_id', string='Consistency Lines',
    )
    filtered_line_ids = fields.Many2many(
        'integration.external.record.consistency.wizard.line', compute='_compute_filtered_line_ids', string='Lines',
    )
    line_status_filter = fields.Selection(
        FILTER_STATUS_SELECTION, string='Show', default=FILTER_STATUS_ALL, required=True,
    )
    checked_count = fields.Integer(string='Checked', compute='_compute_counts')
    missing_count = fields.Integer(string='Missing in Store', compute='_compute_counts')
    unmapped_count = fields.Integer(string='Unmapped', compute='_compute_counts')
    variant_mismatch_count = fields.Integer(string='Variants Mismatch', compute='_compute_counts')
    show_variants = fields.Boolean(compute='_compute_show_variants')

    @property
    def missing_lines(self):
        return self.line_ids.filtered(lambda line: line.status == STATUS_MISSING)

    @property
    def unmapped_lines(self):
        return self.line_ids.filtered(lambda line: line.status == STATUS_UNMAPPED)

    @api.depends('line_ids', 'line_ids.status')
    def _compute_counts(self):
        for wizard in self:
            status_counts = {}
            for line in wizard.line_ids:
                status_counts[line.status] = status_counts.get(line.status, 0) + 1
            wizard.checked_count = len(wizard.line_ids)
            wizard.missing_count = status_counts.get(STATUS_MISSING, 0)
            wizard.unmapped_count = status_counts.get(STATUS_UNMAPPED, 0)
            wizard.variant_mismatch_count = status_counts.get(STATUS_VARIANT_MISMATCH, 0)

    @api.depends('entity_id.external_model')
    def _compute_show_variants(self):
        for wizard in self:
            wizard.show_variants = wizard.entity_id.external_model in VARIANT_MISMATCH_EXTERNAL_MODELS

    @api.depends('line_ids', 'line_ids.status', 'line_status_filter')
    def _compute_filtered_line_ids(self):
        for wizard in self:
            wizard.filtered_line_ids = (
                wizard.line_ids
                if wizard.line_status_filter == FILTER_STATUS_ALL
                else wizard.line_ids.filtered(lambda line: line.status == wizard.line_status_filter)
            )

    @api.onchange('entity_id')
    def _onchange_entity_id(self):
        self.line_ids = False
        self.line_status_filter = FILTER_STATUS_ALL

    def action_check_consistency(self):
        self.ensure_one()
        self._check_consistency_access()

        ExternalModel = self._get_external_model_for_consistency()
        self.line_ids.unlink()
        self.line_ids = self._prepare_consistency_line_commands(ExternalModel)
        return self._action_open()

    def action_open_missing_records(self):
        self.ensure_one()

        self._check_consistency_access()

        if not self.entity_id.external_model:
            return self._action_open()

        return {
            'type': 'ir.actions.act_window',
            'name': _('Missing External Records'),
            'res_model': self.entity_id.external_model,
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.missing_lines.mapped('external_record_id'))],
            'target': 'current',
        }

    def _action_open(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('External Records Consistency Check'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _ensure_supported_external_model(self, ExternalModel):
        missing_fields = [
            field_name for field_name in ('integration_id', 'code') if field_name not in ExternalModel._fields
        ]
        if missing_fields:
            raise UserError(_(
                'The model "%(model)s" cannot be validated because it does not have required fields: %(fields)s.'
            ) % {
                'model': ExternalModel._description,
                'fields': ', '.join(missing_fields),
            })

    def _get_external_model_for_consistency(self):
        entity = self.entity_id
        if not entity:
            raise UserError(_('Please select an entity to check consistency.'))

        if not entity.external_model or entity.external_model not in self.env:
            raise UserError(_('External model for "%s" is not available.') % entity.name)

        ExternalModel = self.env[entity.external_model]
        self._ensure_supported_external_model(ExternalModel)
        return ExternalModel

    def _prepare_consistency_line_commands(self, ExternalModel):
        records = ExternalModel.search([('integration_id', '=', self.integration_id.id)], order='id asc')
        current_codes = self._get_current_store_codes()
        mapping_cache = {}
        return [
            (0, 0, self._prepare_line_vals(record, current_codes, mapping_cache))
            for record in records
        ]

    def action_open_unmapped_records(self):
        self.ensure_one()

        self._check_consistency_access()

        if not self.entity_id.external_model:
            return self._action_open()

        return {
            'type': 'ir.actions.act_window',
            'name': _('Unmapped External Records'),
            'res_model': self.entity_id.external_model,
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.unmapped_lines.mapped('external_record_id'))],
            'target': 'current',
        }

    def _get_current_store_codes(self):
        self.ensure_one()

        adapter_method_name = self.entity_id.consistency_method_name
        if not adapter_method_name:
            raise UserError(_(
                'Consistency check is not configured for "%s".'
            ) % self.entity_id.name)

        method = getattr(self.integration_id.adapter, adapter_method_name, None)
        if not method:
            raise UserError(_(
                'Adapter method "%(method)s" for "%(entity)s" is not available.'
            ) % {
                'method': adapter_method_name,
                'entity': self.entity_id.name,
            })

        return self._extract_store_codes(method())

    def _extract_store_codes(self, data):
        if not data:
            return set()

        if hasattr(data, 'mapped'):
            return set(str(code) for code in (data.mapped('code') or data.ids) if code)

        if isinstance(data, Mapping):
            return self._extract_store_codes_from_mapping(data)

        if isinstance(data, (int, str)):
            return {str(data)}

        if isinstance(data, Iterable):
            return self._extract_store_codes_from_iterable(data)

        return self._extract_store_codes_from_object(data)

    def _extract_store_codes_from_mapping(self, data):
        direct_codes = {
            str(data[key])
            for key in ('id', 'code', 'external_id')
            if key in data and data[key] not in (False, None, '')
        }
        if direct_codes:
            return direct_codes

        codes = set()
        for key, value in data.items():
            if isinstance(key, int) or (isinstance(key, str) and key.isdigit()):
                codes.add(str(key))
            codes.update(self._extract_store_codes(value))
        return codes

    def _extract_store_codes_from_iterable(self, data):
        return {code for value in data for code in self._extract_store_codes(value)}

    def _extract_store_codes_from_object(self, data):
        return {
            str(value)
            for field_name in ('id', 'code', 'external_id')
            for value in [getattr(data, field_name, False)]
            if value
        }

    def _check_consistency_access(self):
        if not self.env.user.has_group('integration.group_integration_manager'):
            raise UserError(_('Only integration managers can use this debug tool.'))

    def _prepare_line_vals(self, record, current_codes, mapping_cache):
        mapping = self._get_mapping_for_external_record(
            record,
            self.entity_id.mapping_model,
            mapping_cache=mapping_cache,
        )
        odoo_record = mapping.odoo_record if mapping else self.env['ir.model'].browse()
        external_variant_ids = self._get_external_variant_records(record)
        odoo_variant_ids = self._get_odoo_variant_records(odoo_record)
        has_variant_mismatch = (
            self.show_variants
            and self._variants_differ(external_variant_ids, odoo_variant_ids, mapping_cache)
        )
        status = self._get_line_status(
            record.code not in current_codes,
            self._is_record_not_mapped(mapping, odoo_record),
            has_variant_mismatch,
        )
        return {
            'external_model': record._name,
            'external_record_id': record.id,
            'code': record.code,
            'status': status,
            'status_priority': STATUS_PRIORITY[status],
            'external_variant_ids': [(6, 0, external_variant_ids.ids)],
            'odoo_variant_ids': [(6, 0, odoo_variant_ids.ids)],
            'odoo_model': odoo_record._name if odoo_record else '',
            'odoo_record_id': odoo_record.id if odoo_record else False,
        }

    def _get_mapping_for_external_record(self, external_record, mapping_model_name=False, mapping_cache=None):
        mapping_model_name = mapping_model_name or self._get_mapping_model_name(external_record._name)
        if not mapping_model_name or mapping_model_name not in self.env:
            return self.env['ir.model'].browse()

        cache_key = (mapping_model_name, external_record.id)
        if mapping_cache is not None and cache_key in mapping_cache:
            return mapping_cache[cache_key]

        MappingModel = self.env[mapping_model_name]
        if not hasattr(MappingModel, '_mapping_fields'):
            return MappingModel.browse()

        __, external_field_name = MappingModel._mapping_fields
        mapping = MappingModel.search([
            ('integration_id', '=', self.integration_id.id),
            (external_field_name, '=', external_record.id),
        ], limit=1)
        if mapping_cache is not None:
            mapping_cache[cache_key] = mapping
        return mapping

    def _get_mapping_model_name(self, external_model_name):
        entity = self.env['integration.import.entity'].search([
            ('external_model', '=', external_model_name),
            ('integration_type', '=', self.integration_type),
        ], limit=1) or self.env['integration.import.entity'].search([
            ('external_model', '=', external_model_name),
            ('integration_type', '=', False),
        ], limit=1)
        if entity.mapping_model:
            return entity.mapping_model
        return external_model_name.replace('.external', '.mapping')

    def _get_line_status(self, is_missing, is_not_mapped, has_variant_mismatch):
        if is_missing:
            return STATUS_MISSING
        if is_not_mapped:
            return STATUS_UNMAPPED
        if has_variant_mismatch:
            return STATUS_VARIANT_MISMATCH
        return STATUS_OK

    def _is_record_not_mapped(self, mapping, odoo_record):
        return bool(self.entity_id.mapping_model) and (not mapping or not odoo_record)

    def _get_record_keys(self, records):
        return set((record._name, record.id) for record in records)

    def _variants_differ(self, external_variants, odoo_variants, mapping_cache=None):
        if not external_variants and not odoo_variants:
            return False
        return (
            self._get_mapped_variant_keys(external_variants, mapping_cache)
            != self._get_record_keys(odoo_variants)
        )

    def _get_mapped_variant_keys(self, external_variants, mapping_cache=None):
        keys = set()
        for external_variant in external_variants:
            mapping = self._get_mapping_for_external_record(external_variant, mapping_cache=mapping_cache)
            if not mapping or not mapping.odoo_record:
                keys.add(('unmapped', external_variant._name, external_variant.id))
                continue
            keys.add((mapping.odoo_record._name, mapping.odoo_record.id))
        return keys

    def _get_external_variant_records(self, record):
        if record._name == 'integration.product.template.external':
            return record.external_product_variant_ids
        return self.env['integration.product.product.external']

    def _get_odoo_variant_records(self, record):
        if record and record._name == 'product.template':
            return record.product_variant_ids
        return self.env['product.product']


class IntegrationExternalRecordConsistencyWizardLine(models.TransientModel):
    _name = 'integration.external.record.consistency.wizard.line'
    _description = 'External Records Consistency Check Line'
    _order = 'status_priority asc, code asc'

    wizard_id = fields.Many2one('integration.external.record.consistency.wizard', required=True, ondelete='cascade')
    external_model = fields.Char(readonly=True)
    external_record_id = fields.Integer(string='External Record ID', readonly=True)
    external_record_ref = fields.Reference(
        selection='_get_reference_model_selection',
        string='External Record Reference',
        compute='_compute_record_refs',
        readonly=True,
    )
    code = fields.Char(string='External ID', readonly=True)
    status = fields.Selection(selection=LINE_STATUS_SELECTION, readonly=True)
    status_priority = fields.Integer(readonly=True)
    can_delete = fields.Boolean(compute='_compute_can_delete')
    odoo_model = fields.Char(readonly=True)
    odoo_record_id = fields.Integer(string='Odoo ID', readonly=True)
    odoo_record_ref = fields.Reference(
        selection='_get_reference_model_selection',
        string='Odoo Record',
        compute='_compute_record_refs',
        readonly=True,
    )
    external_variant_ids = fields.Many2many(
        comodel_name='integration.product.product.external',
        relation='integration_external_record_consistency_external_variant_rel',
        column1='line_id',
        column2='variant_id',
        string='Store Variants',
        readonly=True,
    )

    odoo_variant_ids = fields.Many2many(
        comodel_name='product.product',
        relation='integration_external_record_consistency_odoo_variant_rel',
        column1='line_id',
        column2='variant_id',
        string='Odoo Variants',
        readonly=True,
    )

    @api.depends('status')
    def _compute_can_delete(self):
        for line in self:
            line.can_delete = line.status == STATUS_MISSING

    @api.depends('external_model', 'external_record_id', 'odoo_model', 'odoo_record_id')
    def _compute_record_refs(self):
        for line in self:
            line.external_record_ref = (
                f'{line.external_model},{line.external_record_id}'
                if line.external_model and line.external_record_id else False
            )
            line.odoo_record_ref = (
                f'{line.odoo_model},{line.odoo_record_id}'
                if line.odoo_model and line.odoo_record_id else False
            )

    @api.model
    def _get_reference_model_selection(self):
        return [
            (model.model, model.name)
            for model in self.env['ir.model'].sudo().search([], order='name asc')
        ]

    def action_delete_external_record(self):
        self.ensure_one()
        self.wizard_id._check_consistency_access()
        self._delete_external_record()
        return self.wizard_id._action_open()

    def _delete_external_record(self):
        record = self._get_external_record_for_delete()
        if record and record.code in self.wizard_id._get_current_store_codes():
            raise UserError(_(
                'The external record "%s" exists in the store now. '
                'Please run consistency check one more time before deleting it.'
            ) % record.display_name)

        if record:
            record.unlink()
        self.write({
            'status': STATUS_DELETED,
            'status_priority': STATUS_PRIORITY[STATUS_DELETED],
        })

    def _get_external_record_for_delete(self):
        wizard = self.wizard_id
        wizard._check_consistency_access()

        if self.external_model != wizard.entity_id.external_model:
            raise UserError(_('This line does not match the selected consistency entity.'))
        if self.external_model not in self.env:
            raise UserError(_('External model "%s" is not available.') % self.external_model)

        record = self.env[self.external_model].browse(self.external_record_id).exists()
        if record and record.integration_id != wizard.integration_id:
            raise UserError(_('This external record belongs to another e-commerce store.'))
        return record
