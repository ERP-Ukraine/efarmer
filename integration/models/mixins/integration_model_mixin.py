# See LICENSE file for full copyright and licensing details.

from odoo import models, api

from ...exceptions import NotMappedToExternal


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
        except NotMappedToExternal:
            return self.export_with_integration(integration)

    def to_external_record_or_export(self, integration):
        self.ensure_one()
        try:
            return self.to_external_record(integration)
        except NotMappedToExternal:
            return self.export_with_integration_to_record(integration)

    def to_export_format_or_export(self, integration):
        self.ensure_one()
        try:
            self.to_external(integration)
        except NotMappedToExternal:
            self.export_with_integration(integration)

        return self.to_export_format(integration)

    def to_export_format(self):
        raise NotImplementedError

    def export_with_integration(self):
        """Return external code."""
        raise NotImplementedError

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

        # 1. If translations are not needed, return the field value in the store language
        if not integration.is_translations_needed():
            return self.get_field_value_in_store_language(integration_id, field_name)

        # 2. If translations are needed, convert field into the dict with translations
        language_mappings = self.env['integration.res.lang.mapping'].search([
            ('integration_id', '=', integration_id),
        ])

        translations = {}
        for language_mapping in language_mappings:
            odoo_code = language_mapping.language_id.code
            value = getattr(self.with_context(lang=odoo_code), field_name)

            external_code = language_mapping.external_language_id.code
            translations[external_code] = value

        return {'language': translations}

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

    def _prepare_default_integration_ids(self):
        integrations = self.get_active_integrations()
        integrations_to_apply = integrations.filtered('apply_to_products')
        return [(6, 0, integrations_to_apply.ids)]

    def _get_next_sequence(self):
        sequence_list = self.value_ids.mapped('sequence')
        return max(sequence_list, default=0) + 1

    def _get_description_id_name(self):
        return self._description, self.id, self.display_name
