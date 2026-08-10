# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, _

from ...exceptions import ErrorStore as es


class IntegrationSaleSubStatusExternal(models.Model):
    _name = 'integration.sale.order.sub.status.external'
    _inherit = ['integration.external.mixin', 'integration.workflow.automation.mixin']
    _description = 'E-commerce Order Status Configuration'
    _odoo_model = 'sale.order.sub.status'

    # Override this field from external mixin to provide custom name
    name = fields.Char(
        string='Order Status',
        help='Name of the order status as it appears in the e-commerce system',
    )

    def action_open_workflow_wizard(self):
        """Open the automation wizard, pre-filled with this status's current settings."""
        self.ensure_one()
        type_labels = dict(
            self.env['sale.integration']._fields['type_api']._description_selection(self.env)
        )
        integration = self.integration_id
        title = ' › '.join(filter(None, [
            type_labels.get(integration.type_api),
            integration.name,
            self.name,
        ]))
        wizard = self.env['integration.sale.order.sub.status.bulk.wizard'].create({
            'sub_status_ids': [(6, 0, self.ids)],
            'validate_order': self.validate_order,
            'apply_advance_payment': self.apply_advance_payment,
            'validate_picking': self.validate_picking,
            'create_invoice': self.create_invoice,
            'invoice_journal_id': self.invoice_journal_id.id,
            'invoice_date_source': self.invoice_date_source,
            'validate_invoice': self.validate_invoice,
            'send_invoice': self.send_invoice,
            'register_payment': self.register_payment,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': title,
            'res_model': wizard._name,
            'res_id': wizard.id,
            'view_mode': 'form',
            'views': [(
                self.env.ref(
                    'integration.integration_sale_order_sub_status_bulk_wizard_view_form'
                ).id,
                'form',
            )],
            'target': 'new',
        }

    def retrieve_active_workflow_tasks(self):
        """
        Get the list of active workflow tasks with their priorities.

        Returns:
            list: List of tuples (task_name, is_active, priority)
        """
        self.ensure_one()

        active_task_list = list()
        for idx, task_name in enumerate(self._get_workflow_task_list(), start=1):
            task_enable = True if getattr(self, task_name) else False
            active_task_list.append((task_name, task_enable, idx))

        return active_task_list

    def unlink(self):
        """Delete associated Odoo statuses when external status is removed"""
        if not self.env.context.get('skip_other_delete', False):
            sub_status_mapping_model = self.mapping_model
            for external_status in self:
                sub_statuses_mappings = sub_status_mapping_model.search([
                    ('external_id', '=', external_status.id)
                ])
                for mapping in sub_statuses_mappings:
                    mapping.odoo_id.with_context(skip_other_delete=True).unlink()
        return super(IntegrationSaleSubStatusExternal, self).unlink()

    def _fix_unmapped(self, adapter_external_data):
        """
        Fix unmapped order statuses by creating missing Odoo records.

        Args:
            adapter_external_data: External data from the e-commerce system
        """
        integration = self.integration_id
        # Order statuses should be pre-created automatically in Odoo
        unmapped_sub_statuses = self.mapping_model.search([
            ('integration_id', '=', integration.id),
            ('odoo_id', '=', False),
        ])

        odoo_sub_status_model = self.env['sale.order.sub.status']

        external_values = integration.adapter.get_sale_order_statuses()

        # Handle single record case
        if not isinstance(external_values, list):
            external_values = [external_values]

        # Bind the integration language so the translatable status name is matched against the translation it was
        # stored under at import time; otherwise the search uses the runtime user's language and silently misses
        # matches in multi-language setups. Falls back to the current context language when the integration language
        # is not configured yet.
        lang_context = integration.get_integration_lang_context()

        for mapping in unmapped_sub_statuses:
            odoo_sub_status = odoo_sub_status_model.with_context(**lang_context).search([
                ('name', '=', mapping.external_id.name),
                ('integration_id', '=', integration.id),
            ])

            if not odoo_sub_status:
                # Find status in external data
                external_value = [x for x in external_values if x['id'] == mapping.external_id.code]

                if external_value:
                    external_value = external_value[0]
                else:
                    continue

                create_vals = {
                    'code': external_value.get('external_value'),
                    'integration_id': integration.id,
                    'name': self.env['integration.res.lang.mapping'].convert_external_translations(
                        integration.id,
                        external_value['name'],
                    ),
                }

                odoo_sub_status = self.create_or_update_with_translations(
                    integration.id,
                    odoo_sub_status_model,
                    create_vals,
                )
            if len(odoo_sub_status) == 1:
                mapping.odoo_id = odoo_sub_status.id

    def import_statuses(self):
        """Import order statuses from all e-commerce systems"""
        integrations = self.mapped('integration_id')

        for integration in integrations:
            # Import statuses from E-Commerce System
            external_values = integration.adapter.get_sale_order_statuses()

            for status in self.filtered(lambda x: x.integration_id == integration):
                status.import_status(external_values)

    def import_status(self, external_values):
        """
        Import a single order status from external data.

        Args:
            external_values: External status data from the e-commerce system
        """
        self.ensure_one()

        OrderStatus = self.odoo_model
        MappingStatus = self.mapping_model

        # Try to find existing and mapped status
        mapping = MappingStatus.search([('external_id', '=', self.id)])

        # If mapping doesn't exist, try to find status by name
        if not mapping or not mapping.odoo_id:
            # Bind the integration language so the translatable status name is matched against the translation it
            # was stored under at import time; otherwise the search uses the runtime user's language and silently
            # misses matches in multi-language setups. Falls back to the current context language when the
            # integration language is not configured yet.
            lang_context = self.integration_id.get_integration_lang_context()
            odoo_status = OrderStatus.with_context(**lang_context).search([
                ('name', '=', self.name),
                ('integration_id', '=', self.integration_id.id),
            ])

            if len(odoo_status) > 1:
                raise es.UserError(_(
                    'Multiple order statuses with the name "%s" were found. Please ensure that status names '
                    'are unique within each integration to avoid conflicts.'
                ) % self.name)

            if odoo_status:
                raise es.UserError(_(
                    'An order status with the name "%s" already exists for this integration. '
                    'Please use a different name to avoid duplication.'
                ) % self.name)
        else:
            odoo_status = mapping.odoo_id

        # Handle single record case
        if not isinstance(external_values, list):
            external_values = [external_values]

        # Find status in external data
        external_value = [x for x in external_values if x['id'] == self.code]

        if external_value:
            external_value = external_value[0]
            name = self.env['integration.res.lang.mapping'] \
                .convert_external_translations(self.integration_id.id, external_value['name'])

            odoo_status = self.create_or_update_with_translations(
                self.integration_id.id,
                odoo_status,
                {'name': name},
            )

            self.create_or_update_mapping(odoo_id=odoo_status.id)
