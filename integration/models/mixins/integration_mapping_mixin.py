# See LICENSE file for full copyright and licensing details.

from odoo import models, api, fields, _
from odoo.exceptions import ValidationError

from ...exceptions import NotMappedFromExternal, NotMappedToExternal


class IntegrationMappingMixin(models.AbstractModel):
    _name = 'integration.mapping.mixin'
    _description = 'Integration Mapping Mixin'
    _mapping_fields = (None, None)

    integration_id = fields.Many2one(
        string='E-Commerce Store',
        comodel_name='sale.integration',
        required=True,
        ondelete='cascade',
    )

    company_id = fields.Many2one(
        related='integration_id.company_id',
    )

    type_api = fields.Selection(
        related='integration_id.type_api',
    )

    def show_unmapped_object(self):
        internal_field_id, external_field_id = self._mapping_fields

        unmapped_ids = self.search([
            (internal_field_id, '=', False),
        ])

        return {
            'type': 'ir.actions.act_window',
            'name': self._description,
            'res_model': self._name,
            'view_mode': 'list',
            'domain': [('id', 'in', unmapped_ids.ids)],
            'target': 'current',
        }

    def write(self, vals):
        result = super().write(vals)
        self.requeue_jobs_if_needed()
        return result

    @api.model_create_multi
    def create(self, vals):
        result = super().create(vals)
        result.requeue_jobs_if_needed()
        return result

    def requeue_jobs_if_needed(self):
        QueueJob = self.env['queue.job']

        for mapping in self:
            internal_field_name, external_field_name = self._mapping_fields

            internal_rec = getattr(mapping, internal_field_name)
            external_rec = getattr(mapping, external_field_name)

            if internal_rec and external_rec:
                QueueJob.requeue_integration_jobs(
                    'NotMappedFromExternal',
                    mapping._name,
                    external_rec.code,
                )

                QueueJob.requeue_integration_jobs(
                    'NotMappedToExternal',
                    self._name,
                    str(internal_rec.id),
                )

    @property
    def odoo_record(self):
        internal_field_name, __ = self._mapping_fields
        return getattr(self, internal_field_name)

    @property
    def external_record(self):
        __, external_field_name = self._mapping_fields
        return getattr(self, external_field_name)

    @property
    def odoo_model(self):
        return self.odoo_record.browse()

    @property
    def external_model(self):
        return self.external_record.browse()

    def _retrieve_external_vals(self, integration, odoo_value, code):
        return {
            'integration_id': integration.id,
            'code': code,
        }

    @api.model
    def create_integration_mapping(self, integration, odoo_value, code, extra_vals=None):
        """Integration Mapping --> Integration External"""
        internal_field_name, external_field_name = self._mapping_fields

        external_vals = self._retrieve_external_vals(integration, odoo_value, code)

        if external_vals and isinstance(extra_vals, dict):
            external_vals.update(extra_vals)

        external = self.external_model.create_or_update(external_vals)

        mapping = self.search([
            ('integration_id', '=', integration.id),
            (external_field_name, '=', external.id),
        ])

        if mapping:
            mapping_external = getattr(mapping, external_field_name)
            assert mapping_external.code == code, (mapping_external.code, code)  # noqa
            setattr(mapping, internal_field_name, odoo_value.id)
            return mapping

        mapping = self.create({
            'integration_id': integration.id,
            internal_field_name: odoo_value.id,
            external_field_name: external.id,
        })

        return mapping

    @api.model
    def get_mapping(self, integration, code):
        if not code:
            return self.browse()

        external = self.external_model.search([
            ('integration_id', '=', integration.id),
            ('code', '=', code),
        ])
        return self._search_mapping_from_external(integration, external)

    @api.model
    def get_mapping_from_name(self, integration, name):
        external = self.external_model.search([
            ('integration_id', '=', integration.id),
            ('name', '=', name),
        ])
        return self._search_mapping_from_external(integration, external)

    def _search_mapping_from_external(self, integration, external):
        if not external:
            return self.browse()

        if len(external) > 1:
            conflicting = ', '.join('"%s"' % name for name in external.mapped('display_name'))
            raise ValidationError(_(
                'More than one record in your store "%(store)s" matches the same value, '
                'so Odoo cannot decide which one to link to.\n\n'
                'This is usually caused by duplicated records in the store that share the same '
                '"Name" (for example two attributes both named "Color").\n\n'
                'Conflicting records: %(conflicting)s\n\n'
                'How to fix it:\n'
                '  1. In your store, make sure there are no duplicated records with the same name '
                'and remove any duplicates.\n'
                '  2. In Odoo, remove the duplicated external records:\n'
                '     E-Commerce Integrations -> External Records -> (the entity listed above) and '
                'delete the duplicates.\n'
                '  3. Alternatively, remove all external records and re-import them so they are up to date:\n'
                '     E-Commerce Integrations -> %(store)s -> Data Import -> Open Import Wizard.\n'
                '  4. Retry the failed action or restart the failed job.\n\n'
                'If the problem continues, please contact our support team: https://support.ventor.tech'
            ) % {
                'store': integration.name,
                'conflicting': conflicting,
            })

        __, external_field_name = self._mapping_fields

        mapping = self.search([
            ('integration_id', '=', integration.id),
            (external_field_name, '=', external.id),
        ])
        return mapping

    @api.model
    def to_odoo(self, integration, code, raise_error=True):
        mapping = self.get_mapping(integration, code)
        return self._get_internal_record(mapping, integration, code, raise_error)

    @api.model
    def to_odoo_from_name(self, integration, name, raise_error=True):
        mapping = self.get_mapping_from_name(integration, name)
        return self._get_internal_record(mapping, integration, name, raise_error)

    def _get_internal_record(self, mapping, integration, code, raise_error=True):
        internal_field_name, __ = self._mapping_fields
        record = getattr(mapping, internal_field_name)

        if not record and raise_error:
            raise NotMappedFromExternal(_(
                'The value "%(code)s" coming from your store is not linked to any record in Odoo yet, '
                'so the import cannot continue.\n\n'
                'This happens when the value exists in your store but the matching Odoo record was '
                'never imported or never mapped to it.\n\n'
                'How to fix it:\n'
                '  1. Open the mapping for this entity in Odoo '
                '(E-Commerce Integrations -> Mappings -> the entity listed above) and link the '
                'external value "%(code)s" to the correct Odoo record.\n'
                '  2. If the value is missing entirely, re-import the records from your store '
                '(E-Commerce Integrations -> %(store)s -> Data Import -> Open Import Wizard) and map it.\n'
                '  3. Retry the failed action or restart the failed job.\n\n'
                'If the problem continues, please contact our support team: https://support.ventor.tech'
            ) % {
                'code': code,
                'store': integration.name,
            }, model_name=self._name, code=code, integration=integration)

        return record

    @api.model
    def to_external_record(self, integration, odoo_value, raise_error=True):
        internal_field_name, external_field_name = self._mapping_fields

        mapping = self.search([
            ('integration_id', '=', integration.id),
            (internal_field_name, '=', odoo_value.id),
        ], order='id desc', limit=1)

        if not mapping and raise_error:
            raise NotMappedToExternal(
                _('The Odoo record "%s" has not been exported to your store yet, '
                  'so there is no matching record in the store to link it to.') % odoo_value.display_name,
                model_name=odoo_value._name,
                obj_id=odoo_value.id,
                integration=integration,
            )
        record = getattr(mapping, external_field_name)
        return record

    @api.model
    def to_external(self, integration, odoo_value):
        record = self.to_external_record(integration, odoo_value)
        return record.code

    def bind_odoo(self, record):
        self.ensure_one()
        internal_field_name, _ = self._mapping_fields
        self[internal_field_name] = record

    def clear_mappings(self, integration, records=None):
        internal_field_name, __ = self._mapping_fields

        domain = [
            ('integration_id', '=', integration.id),
        ]
        if records:
            domain.append((internal_field_name, 'in', records.ids))

        mappings = self.search(domain)
        mappings.unlink()

    def _unmap(self):
        internal_field_name, __ = self._mapping_fields
        self.write({internal_field_name: False})
