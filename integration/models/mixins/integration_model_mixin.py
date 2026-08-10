# See LICENSE file for full copyright and licensing details.

from odoo import models, api

from ...exceptions import ErrorStore as es


class IntegrationModelMixin(models.AbstractModel):
    _name = 'integration.model.mixin'
    _description = 'Integration Model Mixin'

    def get_external_code(self, int_id: int):
        self.ensure_one()
        integration = self.env['sale.integration'].browse(int_id)
        record = self.to_external_record(integration, raise_error=False)
        return record.code if record else None

    def to_external(self, integration):
        self.ensure_one()
        mapping_model = self.env[f'integration.{self._name}.mapping']
        return mapping_model.to_external(integration, self)

    def to_external_record(self, integration, raise_error=True):
        self.ensure_one()
        mapping_model = self.env[f'integration.{self._name}.mapping']
        return mapping_model.to_external_record(integration, self, raise_error=raise_error)

    def to_external_or_export(self, integration):
        self.ensure_one()
        try:
            return self.to_external(integration)
        except es.NotMappedToExternal:
            return self.export_with_integration(integration)

    def to_external_record_or_export(self, integration):
        self.ensure_one()
        try:
            return self.to_external_record(integration)
        except es.NotMappedToExternal:
            return self.export_with_integration_to_record(integration)

    def to_export_format_or_export(self, integration):
        self.ensure_one()
        try:
            self.to_external(integration)
        except es.NotMappedToExternal:
            self.export_with_integration(integration)

        return self.to_export_format(integration)

    def to_export_format(self, integration: 'models.Model'):
        es.raise_error('E111')

    def export_with_integration(self, integration: 'models.Model'):
        """Return external code."""
        es.raise_error('E111')

    def export_with_integration_to_record(self, integration):
        self.export_with_integration(integration)
        return self.to_external_record(integration)

    @api.model
    def from_external(self, integration, code, raise_error=True):
        mapping_model = self.env[f'integration.{self._name}.mapping']
        return mapping_model.to_odoo(integration, code, raise_error)

    @api.model
    def from_external_name(self, integration, name, raise_error=True):
        mapping_model = self.env[f'integration.{self._name}.mapping']
        return mapping_model.to_odoo_from_name(integration, name, raise_error)

    def convert_field_translations_to_external(self, integration_id: int, field_name: str):
        integration = self.env['sale.integration'].browse(integration_id)
        return integration.build_external_language_translations(self, field_name)

    def get_field_value_in_store_language(self, integration_id: int, field_name: str):
        integration = self.env['sale.integration'].browse(integration_id)

        lang_code = integration.adapter.lang
        language = self.env['res.lang'].from_external(integration, lang_code)

        return getattr(self.with_context(lang=language.code), field_name)

    def create_mapping(self, integration, code, extra_vals=None):
        """Odoo --> Integration Mapping"""
        mapping_model = self.env[f'integration.{self._name}.mapping']
        mapping = mapping_model.create_integration_mapping(
            integration,
            self,
            code,
            extra_vals=extra_vals,
        )
        return mapping

    def get_mapping(self, integration, code):
        mapping_model = self.env[f'integration.{self._name}.mapping']
        mapping = mapping_model.get_mapping(integration, code)
        return mapping

    def clear_mappings(self, integration):
        mapping_model = self.env[f'integration.{self._name}.mapping']
        mapping_model.clear_mappings(integration, self)

    def get_active_integrations(self):
        active_integrations = self.env['sale.integration'].search([
            ('state', '=', 'active'),
        ])
        return active_integrations

    def _get_next_sequence(self):
        sequence_list = self.value_ids.mapped('sequence')
        return max(sequence_list, default=0) + 1

    def _get_description_id_name(self):
        return self._description, self.id, self.display_name
