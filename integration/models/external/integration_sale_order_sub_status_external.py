# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class IntegrationSaleSubStatusExternal(models.Model):
    _name = 'integration.sale.order.sub.status.external'
    _inherit = 'integration.external.mixin'
    _description = 'E-commerce Order Status Configuration'
    _odoo_model = 'sale.order.sub.status'

    # Override this field from external mixin to provide custom name
    name = fields.Char(
        string='Order Status Name',
        help='Name of the order status as it appears in the e-commerce system',
    )

    validate_order = fields.Boolean(
        string='Confirm Sales Order',
        help='Automatically confirm the sales order when this status is reached',
    )
    validate_picking = fields.Boolean(
        string='Validate Delivery',
        help='Automatically validate the delivery when this status is reached',
    )
    create_invoice = fields.Boolean(
        string='Create Invoice',
        help='Automatically create a customer invoice when this status is reached',
    )
    invoice_journal_id = fields.Many2one(
        comodel_name='account.journal',
        string='Invoice Journal',
        domain="[('type', '=', 'sale'), ('company_id', '=', company_id)]",
        help='Journal to use when creating invoices for this order status',
    )
    validate_invoice = fields.Boolean(
        string='Confirm Invoice',
        help='Automatically confirm the invoice when this status is reached',
    )
    send_invoice = fields.Boolean(
        string='Send Invoice to Customer',
        help='Automatically send the invoice to the customer when this status is reached',
    )
    register_payment = fields.Boolean(
        string='Register Payment',
        help='Automatically register payment when this status is reached',
    )

    @staticmethod
    def _get_workflow_task_list():
        """
        Get the ordered list of workflow tasks.

        Note: The order of tasks is critical for proper workflow execution.

        Returns:
            list: Ordered list of workflow task field names
        """
        return [
            'validate_order',
            'validate_picking',
            'create_invoice',
            'validate_invoice',
            'send_invoice',
            'register_payment',
        ]

    @api.onchange('validate_order')
    def _onchange_validate_order(self):
        """Reset dependent fields when order validation is disabled"""
        if not self.validate_order:
            self.validate_picking = False
            self.create_invoice = False
            self.invoice_journal_id = False
            self.validate_invoice = False
            self.send_invoice = False
            self.register_payment = False

    @api.onchange('create_invoice')
    def _onchange_create_invoice(self):
        """Reset dependent fields when invoice creation is disabled"""
        if not self.create_invoice:
            self.invoice_journal_id = False
            self.validate_invoice = False
            self.send_invoice = False
            self.register_payment = False

    @api.onchange('validate_invoice')
    def _onchange_validate_invoice(self):
        """Reset dependent fields when invoice validation is disabled"""
        if not self.validate_invoice:
            self.send_invoice = False
            self.register_payment = False

    def retrieve_active_workflow_tasks(self):
        """
        Get the list of active workflow tasks with their priorities.

        Returns:
            list: List of tuples (task_name, is_active, priority)
        """
        self.ensure_one()
        task_list = self._get_workflow_task_list()

        active_task_list = list()
        for idx, task_name in enumerate(task_list, start=1):
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

        for mapping in unmapped_sub_statuses:
            odoo_sub_status = odoo_sub_status_model.search([
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
            odoo_status = OrderStatus.search([
                ('name', '=', self.name),
                ('integration_id', '=', self.integration_id.id),
            ])

            if len(odoo_status) > 1:
                raise UserError(_(
                    'Multiple order statuses with the name "%s" were found. Please ensure that status names '
                    'are unique within each integration to avoid conflicts.'
                ) % self.name)

            if odoo_status:
                raise UserError(_(
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
