# See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class IntegrationMappingAny(models.Model):
    _name = 'integration.mapping.any'
    _description = 'Integration Mapping Any'

    integration_id = fields.Many2one(
        comodel_name='sale.integration',
        required=True,
        ondelete='cascade',
    )

    odoo_obj_name = fields.Char(
        string='Odoo Object Name'
    )

    odoo_obj_id = fields.Integer(
        string='Odoo Object ID',
        index=True,
    )

    # It is needed for automatic control on field changing
    odoo_obj_field_name = fields.Char(
        string='Odoo Object Field Name'
    )

    external_obj_name = fields.Char(
        string='External Object Name'
    )

    external_obj_id = fields.Char(
        string='External Object ID',
        index=True,
    )

    def unlink_any_mapping(self, odoo_obj_name, odoo_obj_ids, integration=False):
        if not odoo_obj_name or not odoo_obj_ids:
            return False

        domain = [
            ('odoo_obj_name', '=', odoo_obj_name),
            ('odoo_obj_id', 'in', odoo_obj_ids),
        ]

        if integration:
            domain.append(('integration_id', '=', integration.id))

        any_mapping = self.search(domain)

        return any_mapping.unlink()

    def update_mapping_any(self, integration, odoo_obj_name, odoo_obj_id, odoo_obj_field_name,
                           external_obj_name, external_obj_id):
        any_mapping = self.find_mapping_any(
            integration, odoo_obj_name, odoo_obj_id, external_obj_name)

        if len(any_mapping) > 1:
            any_mapping.unlink()
            any_mapping = False

        vals = {
            'external_obj_id': external_obj_id,
            'odoo_obj_field_name': odoo_obj_field_name,
        }

        if any_mapping:
            any_mapping.update(vals)
        else:
            vals['integration_id'] = integration.id
            vals['odoo_obj_name'] = odoo_obj_name
            vals['odoo_obj_id'] = odoo_obj_id
            vals['external_obj_name'] = external_obj_name

            any_mapping = self.create(vals)

        return any_mapping

    def find_mapping_any(self, integration, odoo_obj_name, odoo_obj_id, external_obj_name):
        search_domain = [
            ('odoo_obj_name', '=', odoo_obj_name),
            ('odoo_obj_id', '=', odoo_obj_id),
        ]

        if external_obj_name:
            search_domain.append(('external_obj_name', '=', external_obj_name))

        if integration:
            search_domain.append(('integration_id', '=', integration.id))

        any_mapping = self.search(search_domain)

        return any_mapping


class MappingAnyMixin(models.AbstractModel):
    _name = 'mapping.any.mixin'
    _description = 'Mapping Any Mixin'

    def unlink(self):
        self.env['integration.mapping.any'].unlink_any_mapping(self._name, self.ids)
        return super(MappingAnyMixin, self).unlink()

    def write(self, vals):
        for obj in self:
            any_mappings = obj.find_mapping_any()

            for any_mapping in any_mappings:
                if any_mapping.odoo_obj_field_name in vals:
                    any_mapping.unlink()

        return super(MappingAnyMixin, self).write(vals)

    def find_mapping_any(self, integration=False, external_obj_name=False):
        any_mapping = self.env['integration.mapping.any'].find_mapping_any(
            integration, self._name, self.id, external_obj_name)

        return any_mapping

    def update_mapping_any(
            self, integration, odoo_obj_field_name, external_obj_name, external_obj_id):
        self.ensure_one()

        MappingAny = self.env['integration.mapping.any']

        if not external_obj_id:
            return MappingAny.unlink_any_mapping(self._name, self.ids)

        return MappingAny.update_mapping_any(integration, self._name, self.id, odoo_obj_field_name,
                                             external_obj_name, external_obj_id)

    def get_mapping_any_external_id(self, integration, external_obj_name):
        self.ensure_one()

        any_mapping = self.find_mapping_any(integration, external_obj_name)

        if any_mapping:
            return any_mapping[0].external_obj_id

        return False
