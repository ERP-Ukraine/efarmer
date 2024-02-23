# See LICENSE file for full copyright and licensing details.

import logging

from odoo import models, api

from ..exceptions import NotMappedToExternal


_logger = logging.getLogger(__name__)


class IntegrationModelMixin(models.AbstractModel):
    _name = 'integration.model.mixin'
    _description = 'Integration Model Mixin'

    @property
    def mrp_enabled(self):
        return self.sudo().env.ref('base.module_mrp').state == 'installed'

    def try_to_external_record(self, integration):
        try:
            return self.to_external_record(integration)
        except NotMappedToExternal:
            return None

    def try_to_external(self, integration):
        try:
            return self.to_external(integration)
        except NotMappedToExternal:
            return None

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

    def export_with_integration_to_record(self):
        """Return external record."""
        raise NotImplementedError

    @api.model
    def from_external(self, integration, code, raise_error=True):
        mapping_model = self.env[f'integration.{self._name}.mapping']
        return mapping_model.to_odoo(integration, code, raise_error)

    @api.model
    def from_external_name(self, integration, name, raise_error=True):
        mapping_model = self.env[f'integration.{self._name}.mapping']
        return mapping_model.to_odoo_from_name(integration, name, raise_error)

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

    def _perform_method_by_name(self, method_name, *args, **kw):
        if hasattr(self, method_name):
            method = getattr(self, method_name)
            if callable(method):
                method(*args, **kw)
                return True
        _logger.warning(
            '%s integration. The %s() method not found.', (self.type_api, method_name)
        )
        return False

    def _get_next_sequence(self):
        sequence_list = self.value_ids.mapped('sequence')
        return max(sequence_list, default=0) + 1
