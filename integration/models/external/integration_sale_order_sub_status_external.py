# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class IntegrationSaleSubStatusExternal(models.Model):
    _name = 'integration.sale.order.sub.status.external'
    _inherit = 'integration.external.mixin'
    _description = 'Integration Sale Sub Status External'
    _odoo_model = 'sale.order.sub.status'

    validate_order = fields.Boolean(
        string='Validate Order',
    )
    validate_picking = fields.Boolean(
        string='Validate Delivery',
    )
    create_invoice = fields.Boolean(
        string='Create Invoice',
    )
    force_invoice_date = fields.Boolean(
        string='Force Invoice Date',
    )
    invoice_journal_id = fields.Many2one(
        comodel_name='account.journal',
        string='Invoice Journal',
        domain="[('type', '=', 'sale')]",
    )
    validate_invoice = fields.Boolean(
        string='Validate Invoice',
    )
    register_payment = fields.Boolean(
        string='Register Payment',
    )

    @staticmethod
    def _get_workflow_task_list():
        """Attention! Order matters!"""
        return [
            'validate_order',
            'validate_picking',
            'create_invoice',
            'validate_invoice',
            'register_payment',
        ]

    @api.onchange('validate_order')
    def _onchange_validate_order(self):
        if not self.validate_order:
            self.validate_picking = False
            self.create_invoice = False
            self.force_invoice_date = False
            self.invoice_journal_id = False
            self.validate_invoice = False
            self.register_payment = False

    @api.onchange('create_invoice')
    def _onchange_create_invoice(self):
        if not self.create_invoice:
            self.force_invoice_date = False
            self.invoice_journal_id = False
            self.validate_invoice = False
            self.register_payment = False

    @api.onchange('validate_invoice')
    def _onchange_validate_invoice(self):
        if not self.validate_invoice:
            self.register_payment = False

    def retrieve_active_workflow_tasks(self):
        """
        return: [(`task name`, `task active`, `task priority`), ...]
        """
        self.ensure_one()
        task_list = self._get_workflow_task_list()

        active_task_list = list()
        for idx, task_name in enumerate(task_list, start=1):
            task_enable = True if getattr(self, task_name) else False
            active_task_list.append((task_name, task_enable, idx))

        return active_task_list

    def unlink(self):
        # Delete all odoo statuses also
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
        integration = self.integration_id
        # Order statuses should be pre-created automatically in Odoo
        unmapped_sub_statuses = self.mapping_model.search([
            ('integration_id', '=', integration.id),
            ('odoo_id', '=', False),
        ])

        odoo_sub_status_model = self.env['sale.order.sub.status']

        external_values = integration._build_adapter().get_sale_order_statuses()

        # in case we only receive 1 record its not added to list as others
        if not isinstance(external_values, list):
            external_values = [external_values]

        for mapping in unmapped_sub_statuses:
            odoo_sub_status = odoo_sub_status_model.search([
                ('name', '=', mapping.external_id.name),
                ('integration_id', '=', mapping.external_id.integration_id.id),
            ])

            if not odoo_sub_status:
                # Find status in external and children of our status
                external_value = [x for x in external_values if x['id'] == mapping.external_id.code]

                if external_value:
                    external_value = external_value[0]
                else:
                    continue

                create_vals = {
                    'code': external_value.get('external_value'),
                    'integration_id': mapping.external_id.integration_id.id,
                    'name': integration.convert_translated_field_to_odoo_format(
                        external_value['name']),
                }

                odoo_sub_status = self.create_or_update_with_translation(
                    integration=integration,
                    odoo_object=odoo_sub_status_model,
                    vals=create_vals,
                )
            if len(odoo_sub_status) == 1:
                mapping.odoo_id = odoo_sub_status.id

    def import_statuses(self):
        integrations = self.mapped('integration_id')

        for integration in integrations:
            # Import statuses from e-Commerce System
            external_values = integration._build_adapter().get_sale_order_statuses()

            for status in self.filtered(lambda x: x.integration_id == integration):
                status.import_status(external_values)

    def import_status(self, external_values):
        self.ensure_one()

        OrderStatus = self.odoo_model
        MappingStatus = self.mapping_model

        # Try to find existing and mapped status
        mapping = MappingStatus.search([('external_id', '=', self.id)])

        # If mapping doesn`t exists try to find status by the name
        if not mapping or not mapping.odoo_id:
            odoo_status = OrderStatus.search([
                ('name', '=', self.name),
                ('integration_id', '=', self.integration_id.id),
            ])

            if len(odoo_status) > 1:
                raise UserError(_('There are several statuses with name "%s"') % self.name)

            if odoo_status:
                raise UserError(_('Status with name "%s" already exists') % self.name)
        else:
            odoo_status = mapping.odoo_id

        # in case we only receive 1 record its not added to list as others
        if not isinstance(external_values, list):
            external_values = [external_values]

        # Find status in external and children of our status
        external_value = [x for x in external_values if x['id'] == self.code]

        if external_value:
            external_value = external_value[0]
            name = self.integration_id.convert_translated_field_to_odoo_format(
                external_value['name'])

            odoo_status = self.create_or_update_with_translation(
                integration=self.integration_id,
                odoo_object=odoo_status,
                vals={'name': name},
            )

            self.create_or_update_mapping(odoo_id=odoo_status.id)
