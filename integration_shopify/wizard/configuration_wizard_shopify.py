#  See LICENSE file for full copyright and licensing details.

from odoo import models, fields, _
from odoo.exceptions import UserError

from ..shopify.resources.order_status import OrderStatus
from ..shopify.resources.order_display_financial_status import OrderDisplayFinancialStatus as OrderFinancialStatus
from ..shopify.resources.order_display_fulfillment_status import OrderDisplayFulfillmentStatus as OrderFulfillmentStatus


class QuickConfigurationShopify(models.TransientModel):
    _name = 'configuration.wizard.shopify'
    _inherit = 'configuration.wizard'
    _description = 'Quick Configuration for Shopify'
    _steps = [
        ('step_intro', 'Introduction'),
        ('step_languages', 'Step 1. Languages Mapping'),
        ('step_order_status', 'Step 2. Select global order statuses for the receive filter'),
        (
            'step_order_financial_status',
            'Step 3. Select order financial statuses for the receive filter',
        ),
        (
            'step_order_fulfillment_status',
            'Step 4. Select order fulfillment statuses for the receive filter',
        ),
        ('step_finish', 'Finish'),
    ]

    state = fields.Char(
        default='step_intro',
    )
    configuration_order_status_ids = fields.One2many(
        comodel_name='configuration.wizard.shopify.line',
        inverse_name='configuration_wizard_id',
        string='Order Statuses',
        domain=lambda self: [
            ('is_order_status', '=', True),
            ('configuration_wizard_id', '=', self.id),
        ],
    )
    configuration_order_financial_status_ids = fields.One2many(
        comodel_name='configuration.wizard.shopify.line',
        inverse_name='configuration_wizard_id',
        string='Order Financial Statuses',
        domain=lambda self: [
            ('is_order_financial_status', '=', True),
            ('configuration_wizard_id', '=', self.id),
        ],
    )
    configuration_order_fulfillment_status_ids = fields.One2many(
        comodel_name='configuration.wizard.shopify.line',
        inverse_name='configuration_wizard_id',
        string='Order Fulfillment Statuses',
        domain=lambda self: [
            ('is_order_fulfillment_status', '=', True),
            ('configuration_wizard_id', '=', self.id),
        ],
    )
    configuration_shopify_line_ids = fields.One2many(
        comodel_name='configuration.wizard.shopify.line',
        inverse_name='configuration_wizard_id',
        string='Configuration Shopify Lines',
        domain=lambda self: [
            ('configuration_wizard_id', '=', self.id),
        ],
    )

    # Step Intro
    def run_before_step_intro(self):
        pass

    # Step Order Status
    def run_before_step_order_status(self):
        self.configuration_order_status_ids.unlink()

        status_list = OrderStatus.to_list()

        vals_list = []
        for data in status_list:
            vals = {
                'is_order_status': True,
                'activate': False,
                'name': data['string'],
                'code': data['name'],
                'info': data['description'],
                'configuration_wizard_id': self.id,
            }
            vals_list.append(vals)

        lines = self.env['configuration.wizard.shopify.line'].create(vals_list)

        existing_value = self.integration_id.get_settings_value(
            'receive_order_statuses',
        )
        if existing_value:
            status_list = existing_value.split(',')
            lines.filtered(lambda x: x.code in status_list).write({
                'activate': True,
            })

    def run_after_step_order_status(self):
        active_status_ids = self.configuration_order_status_ids.filtered('activate')

        if not active_status_ids:
            raise UserError(_(
                'You have to select at least one order status to be imported.'
            ))

        default_status_id = self.configuration_order_status_ids \
            .filtered(lambda x: x.code == OrderStatus.open.name)
        status_ids = active_status_ids or default_status_id

        self.integration_id.set_settings_value(
            'receive_order_statuses',
            ','.join(status_ids.mapped('code')),
        )
        return True

    # Step Order Financial Status
    def run_before_step_order_financial_status(self):
        self.configuration_order_financial_status_ids.unlink()

        vals_list = []
        status_list = OrderFinancialStatus.to_list()

        for data in status_list:
            vals = {
                'is_order_financial_status': True,
                'activate': False,
                'name': data['string'],
                'code': data['name'],
                'info': data['description'],
                'configuration_wizard_id': self.id,
            }
            vals_list.append(vals)

        lines = self.env['configuration.wizard.shopify.line'].create(vals_list)

        existing_value = self.integration_id.get_settings_value(
            'receive_order_financial_statuses',
        )
        if existing_value:
            status_list = existing_value.split(',')
            lines.filtered(lambda x: x.code in status_list).write({
                'activate': True,
            })

    def run_after_step_order_financial_status(self):
        active_status_ids = self.configuration_order_financial_status_ids.filtered('activate')

        if not active_status_ids:
            raise UserError(_(
                'You have to select at least one order financial status to be imported.'
            ))

        default_status_id = self.configuration_order_financial_status_ids \
            .filtered(lambda x: x.code == OrderFinancialStatus.paid.name)

        status_ids = active_status_ids or default_status_id

        self.integration_id.set_settings_value(
            'receive_order_financial_statuses',
            ','.join(status_ids.mapped('code')),
        )
        return True

    # Step Order Fullfillment Status
    def run_before_step_order_fulfillment_status(self):
        self.configuration_order_fulfillment_status_ids.unlink()

        vals_list = []
        status_list = OrderFulfillmentStatus.to_list(exclude=[
            'open',
            'pending_fulfillment',
            'restocked',
            'in_progress',
            'partially_fulfilled',
        ])
        for data in status_list:
            vals = {
                'is_order_fulfillment_status': True,
                'activate': False,
                'name': data['string'],
                'code': data['name'],
                'info': data['description'],
                'configuration_wizard_id': self.id,
            }
            vals_list.append(vals)

        lines = self.env['configuration.wizard.shopify.line'].create(vals_list)

        existing_value = self.integration_id.get_settings_value(
            'receive_order_fulfillment_statuses',
        )
        if existing_value:
            status_list = existing_value.split(',')
            lines.filtered(lambda x: x.code in status_list).write({
                'activate': True,
            })

    def run_after_step_order_fulfillment_status(self):
        active_status_ids = self.configuration_order_fulfillment_status_ids.filtered('activate')

        if not active_status_ids:
            raise UserError(_(
                'You have to select at least one order fulfillment status to be imported.'
            ))

        default_status_id = self.configuration_order_fulfillment_status_ids \
            .filtered(lambda x: x.code == OrderFulfillmentStatus.fulfilled.name)

        status_ids = active_status_ids or default_status_id

        self.integration_id.set_settings_value(
            'receive_order_fulfillment_statuses',
            ','.join(status_ids.mapped('code')),
        )
        return True

    @staticmethod
    def get_form_xml_id():
        return 'integration_shopify.view_configuration_wizard'


class QuickConfigurationShopifyLine(models.TransientModel):
    _name = 'configuration.wizard.shopify.line'
    _description = 'Quick Configuration Shopify Line'

    activate = fields.Boolean(
        string='Activate',
    )
    name = fields.Char(
        string='Name',
    )
    code = fields.Char(
        string='Code',
    )
    info = fields.Char(
        string='Info',
    )
    is_order_status = fields.Boolean(
        string='Is Order Status',
    )
    is_order_financial_status = fields.Boolean(
        string='Is Order Financial Status',
    )
    is_order_fulfillment_status = fields.Boolean(
        string='Is Order Fullfillment Status',
    )
    configuration_wizard_id = fields.Many2one(
        comodel_name='configuration.wizard.shopify',
        ondelete='cascade',
    )
