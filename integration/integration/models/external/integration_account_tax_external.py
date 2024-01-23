# See LICENSE file for full copyright and licensing details.

import logging

from odoo import models, fields


_logger = logging.getLogger(__name__)


class IntegrationAccountTaxExternal(models.Model):
    _name = 'integration.account.tax.external'
    _inherit = 'integration.external.mixin'
    _description = 'Integration Account Tax External'
    _odoo_model = 'account.tax'

    external_tax_group_ids = fields.Many2many(
        comodel_name='integration.account.tax.group.external',
        relation='external_tax_group_to_external_tax_relation',
        column1='external_tax_id',
        column2='external_tax_group_id',
        string='Related External Tax Groups',
        readonly=True,
    )

    def _fix_unmapped(self, adapter_external_data):
        result = list()
        mapping_model = self.mapping_model

        for record, adapter_data in zip(self, adapter_external_data):
            mapping = mapping_model.search([
                ('external_tax_id', '=', record.id),
                ('integration_id', '=', record.integration_id.id),
            ], limit=1)

            if not mapping:
                continue

            odoo_record = mapping._fix_unmapped_tax_one(external_data=adapter_data)
            result.append(odoo_record)

        return result

    def try_map_by_external_reference(self, odoo_search_domain=False):
        self.ensure_one()

        # If we found existing mapping, we do not need to do anything
        if self.odoo_record:
            return

        self.create_or_update_mapping()

    def action_import_taxes_from_external(self):
        for integration in self.mapped('integration_id'):
            adapter_data_list = integration._build_adapter().get_taxes()

            for tax in self.filtered(lambda x: x.integration_id == integration):
                tax.import_tax(adapter_data_list)

    def import_tax(self, adapter_data_list):
        self.ensure_one()
        # in case we only receive 1 record its not added to list as others
        if not isinstance(adapter_data_list, list):
            adapter_data_list = [adapter_data_list]

        # Find tax in external and children of our tax
        adapter_data = [x for x in adapter_data_list if x['id'] == self.code]
        adapter_data = adapter_data and adapter_data[0]
        if not adapter_data:
            return

        mapping = self.create_or_update_mapping()

        return mapping.with_context(force_create_tax=True)\
            ._fix_unmapped_tax_one(external_data=adapter_data)

    def _post_import_external_one(self, adapter_external_record):
        """
        This method will receive individual tax record.
        In case it has tax_groups - they will be created.
        """
        external_tax_groups = adapter_external_record.get('tax_groups')
        if not external_tax_groups:
            return

        all_tax_groups = []
        ExternalTaxGroup = self.env['integration.account.tax.group.external']

        for external_tax_group in external_tax_groups:
            tax_group = ExternalTaxGroup.create_or_update({
                'integration_id': self.integration_id.id,
                'code': external_tax_group['id'],
                'name': external_tax_group['name'],
                'external_reference': external_tax_group.get('external_reference'),
            })
            all_tax_groups.append((4, tax_group.id, 0))

        if all_tax_groups:
            self.external_tax_group_ids = all_tax_groups
