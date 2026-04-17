# See LICENSE file for full copyright and licensing details.

import base64
import logging
import math
import json
from collections import defaultdict
from datetime import datetime, timedelta

from odoo import fields, models, api, SUPERUSER_ID, _
from odoo.tools.float_utils import float_compare
from odoo.tools import float_is_zero
from odoo.exceptions import UserError, ValidationError

from .sale_integration import DATETIME_FORMAT
from .auto_workflow.integration_workflow_pipeline import SKIP, TO_DO
from ...integration.exceptions import ApiImportError


_logger = logging.getLogger(__name__)


def reset_next_value_if_not_previous(task_list):
    """
    Disable workflow task if previous task is disabled.
    This option validates on the form view, but it may be changed on backend.

    :task_list:  # [(`task-name`, `task enable`, ..), ..]
        [('a', True, ..), ('b', False, ..), ('c', True, ..), ('d', True, ..), ..]

    :task_list_updated:
        [('a', True), ('b', False), ('c', False), ('d', False), ..]
    """
    task_list_updated, list_len, reset_index = list(), len(task_list), int()
    for idx, (task_name, task_enable, *__) in enumerate(task_list):
        if not reset_index and (idx + 1) <= list_len and not task_list[idx][1]:
            reset_index = idx + 1

        # if reset_index and idx >= reset_index:
        #     task_enable = False

        task_list_updated.append((task_name, task_enable))

    return task_list_updated


def _prepare_integration_dashboard_condition(start_date, end_date, integration_ids):
    # Only confirmed orders
    query = 'so.state = \'sale\''

    # Date range conditions
    query += ' AND so.date_order >= %s'
    condition_params = [start_date]

    end_date_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
    end_date_str = end_date_dt.strftime('%Y-%m-%d')
    query += ' AND so.date_order < %s'
    condition_params.append(end_date_str)

    # Imported from specific stores
    query += ' AND so.integration_id IN %s'
    condition_params.append(tuple(integration_ids))

    return query, condition_params


class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['sale.order', 'integration.model.mixin']

    integration_id = fields.Many2one(
        string='E-Commerce Store',
        comodel_name='sale.integration',
        readonly=True,
        copy=False,
    )

    integration_delivery_note = fields.Text(
        string='E-Commerce Delivery Note',
        copy=False,
    )

    external_sales_order_ref = fields.Char(
        string='E-Commerce Order Reference',
        compute='_compute_external_sales_order_ref',
        readonly=True,
        store=True,
        help='This is the reference of the order in the E-Commerce System.',
    )

    external_payment_ids = fields.One2many(
        comodel_name='external.order.transaction',
        inverse_name='erp_order_id',
        string='Payments',
    )

    external_fulfillment_ids = fields.One2many(
        comodel_name='external.order.fulfillment',
        inverse_name='erp_order_id',
        string='Fulfillments',
        copy=False,
    )

    related_input_files = fields.One2many(
        string='Related input files',
        comodel_name='sale.integration.input.file',
        inverse_name='order_id',
    )

    sub_status_id = fields.Many2one(
        string='E-Commerce Store Order Status',
        comodel_name='sale.order.sub.status',
        domain='[("integration_id", "=", integration_id)]',
        ondelete='set null',
        tracking=True,
        copy=False,
    )

    type_api = fields.Selection(
        string='Api service',
        related='integration_id.type_api',
        help='Technical field',
    )

    payment_method_id = fields.Many2one(
        string='E-Commerce Payment method',
        comodel_name='sale.order.payment.method',
        domain='[("integration_id", "=", integration_id)]',
        ondelete='set null',
        copy=False,
    )

    integration_amount_total = fields.Monetary(
        string='E-Commerce Total Amount',
        copy=False,
    )

    is_total_amount_difference = fields.Boolean(
        compute='_compute_is_total_amount_difference'
    )

    total_amount_difference_error_message = fields.Text(
        string='Error Message',
        compute='_compute_total_amount_difference_error_message',
    )

    is_multi_stock = fields.Boolean(
        compute='_compute_is_multi_stock',
        string='External Multistock',
    )

    @property
    def order_is_confirmed(self):
        assert len(self) <= 1, _('Recordsets not allowed')
        return self.state == 'sale'

    @property
    def order_is_cancelled(self):
        assert len(self) <= 1, _('Recordsets not allowed')
        return self.state == 'cancel'

    @property
    def order_is_invoiced(self):
        assert len(self) <= 1, _('Recordsets not allowed')
        return self.invoice_status == 'invoiced'

    @property
    def order_is_fully_paid(self):
        assert len(self) <= 1, _('Recordsets not allowed')
        return all(x.invoice_is_paid for x in self.actual_invoice_ids)

    @property
    def actual_invoice_ids(self):
        return self.invoice_ids.filtered(lambda x: x.state != 'cancel')

    @property
    def is_order_invoices_posted(self):
        assert len(self) <= 1, _('Recordsets not allowed')
        return self.order_is_invoiced and all(self.actual_invoice_ids.mapped(lambda x: x.invoice_is_posted))

    @property
    def is_procurement_grouped(self):
        assert len(self) <= 1, _('Recordsets not allowed')
        if not self.order_is_confirmed:
            return False

        external_locations = self._integration_external_locations()
        if not external_locations:
            return False

        warehouse_ids = []
        for external_id in external_locations:
            warehouse = self.integration_id._get_wh_from_external_location(external_id)

            if warehouse:
                warehouse_ids.append(warehouse.id)

        pickings = self.picking_ids.filtered(lambda x: x.state != 'cancel')

        return len(set(pickings.mapped('location_id.warehouse_id'))) == len(warehouse_ids)

    @property
    def is_available_multi_stock_for_so(self):
        if not self.integration_id.is_integration_shopify:
            return False

        return self.order_line._fields['warehouse_id'].store

    @property
    def integration_pipeline(self):
        assert len(self) <= 1, _('Recordsets not allowed')
        return self.env['integration.workflow.pipeline'].search([
            ('order_id', '=', self.id),
        ], limit=1)

    @property
    def input_file_id(self):
        return self.related_input_files[:1].id

    @property
    def external_order_name(self):
        assert len(self) <= 1, _('Recordsets not allowed')
        return self.related_input_files[:1].name

    @property
    def external_order_ref(self):
        assert len(self) <= 1, _('Recordsets not allowed')
        return self.related_input_files[:1].order_reference

    @api.depends('amount_total')
    def _compute_total_amount_difference_error_message(self):
        error_message = _(
            'Warning!\n'
            'Difference in total order amounts in E-Commerce System and Odoo.'
            'Total order amount in E-Commerce System is %s. Total order amount in Odoo is %s.')
        for order in self:
            if order.is_total_amount_difference:
                order.total_amount_difference_error_message = error_message % (
                    order.integration_amount_total, order.amount_total)
            else:
                order.total_amount_difference_error_message = ''

    def _get_integration_id_for_job(self):
        return self.integration_id.id

    def _get_file_id_for_log(self):
        return self.related_input_files[:1].id

    def action_cancel(self):
        res = super(SaleOrder, self).action_cancel()
        if res is True:
            for order in self:
                order._integration_cancel_order_hook()
        return res

    def action_integration_pipeline_form(self):
        pipeline = self.integration_pipeline

        # Check if the integration pipeline exists
        if not pipeline:
            raise UserError(_(
                'No related integration workflow pipeline found.'
            ))

        return pipeline.open_form()

    def action_external_order_form(self):
        """
        Opens the form view of the related input file.
        If no related input file exists, raises a UserError.
        """
        self.ensure_one()

        record = self.related_input_files

        if not record:
            return {}

        record.ensure_one()

        return record.get_formview_action()

    def open_job_logs(self):
        self.ensure_one()
        job_log_ids = self.env['job.log'].search([
            ('order_id', '=', self.id),
        ])
        return job_log_ids.open_tree_view()

    def check_is_order_shipped(self):
        """
        This method checks if the order is shipped or not.
        """
        self.ensure_one()
        is_order_shipped = False

        picking_states = [
            x for x in self.picking_ids.mapped('state') if x not in ('cancel', 'done')
        ]
        if all([
            self.state not in ('draft', 'sent', 'cancel'),
            not picking_states,
            self._is_partially_delivered(),
        ]):
            is_order_shipped = True

        return is_order_shipped

    def _is_partially_delivered(self):
        """
        Returns True if all or any lines are delivered
        :returns: boolean
        """
        self.ensure_one()
        # Skip lines with not deliverable products
        sale_lines = self.order_line.filtered(lambda rec: rec._is_deliverable_product())

        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')

        return any(
            not float_is_zero(line.qty_delivered, precision_digits=precision)
            for line in sale_lines
        )

    def write(self, vals):
        statuses_before_write = {}

        if vals.get('sub_status_id'):
            for order in self:
                statuses_before_write[order] = order.sub_status_id

        result = super(SaleOrder, self).write(vals)

        if self.env.context.get('skip_dispatch_to_external'):
            return result

        if vals.get('sub_status_id'):
            for order in self:
                if statuses_before_write[order] == order.sub_status_id:
                    continue

                integration = order.integration_id
                if not integration:
                    continue

                if not integration.is_sale_order_status_export_enabled:
                    continue

                job_kwargs = self._job_kwargs_export_sale_order_status(order)

                job = integration \
                    .with_context(company_id=integration.company_id.id) \
                    .with_delay(**job_kwargs) \
                    .export_sale_order_status(order)

                order.job_log(job)

        return result

    @api.depends('order_line.external_location_id')
    def _compute_is_multi_stock(self):
        for rec in self:
            external_locations = self._integration_external_locations()
            rec.is_multi_stock = len(external_locations) > 1

    @api.depends('amount_total', 'integration_amount_total')
    def _compute_is_total_amount_difference(self):
        for order in self:
            if not order.integration_amount_total:
                order.is_total_amount_difference = False
            else:
                order.is_total_amount_difference = float_compare(
                    value1=order.integration_amount_total,
                    value2=order.amount_total,
                    precision_digits=self.env['decimal.precision'].precision_get('Product Price'),
                ) != 0

    @api.depends('related_input_files')
    def _compute_external_sales_order_ref(self):
        for order in self:
            reference_list = order.related_input_files.mapped('order_reference')
            order.external_sales_order_ref = ', '.join(reference_list) or ''

    def _integration_external_locations(self):
        return set(filter(None, self.order_line.mapped('external_location_id')))

    def _perform_method_by_name(self, method_name, *args, **kw):
        if hasattr(self, method_name):
            method = getattr(self, method_name)

            if callable(method):
                method(*args, **kw)
                return True

        _logger.warning('%s integration. The %s() method not found.', self.type_api, method_name)
        return False

    def _integration_cancel_order_hook(self):
        self.ensure_one()

        if not self.integration_id:
            return None

        if self.integration_id.run_action_on_cancel_so:
            result = self._perform_method_by_name(f'_{self.type_api}_cancel_order')
        else:
            result = None

        # Trigger export of inventory when specific integration settings are enabled
        # This export aims to synchronize the inventory after order cancellation
        if self.integration_id.is_real_time_inventory_export_enabled:
            product_ids = self.mapped('order_line.product_id')

            # Filter out products that should not be synchronized
            product_ids = product_ids.filtered(lambda x: x.integration_should_export_inventory)

            if product_ids:
                product_ids.export_inventory_by_jobs(self.integration_id, cron_operation=False)

        return result

    def _integration_shipped_order_hook(self):
        self.ensure_one()
        if not self.integration_id.run_action_on_shipping_so:
            return None

        return self._perform_method_by_name(f'_{self.type_api}_shipped_order')

    def _integration_validate_invoice_order_hook(self):
        self.ensure_one()
        if not self.integration_id:
            return None

        if self.payment_method_id:
            payment_method_external = self.payment_method_id.to_external_record(self.integration_id)
            action_after_validation = payment_method_external.send_when_invoice_is_validated

            if action_after_validation and all(x.invoice_is_posted for x in self.actual_invoice_ids):
                _logger.info(
                    '%s: force export paid status for %s to external.', self.integration_id.name, self
                )
                return self.with_context(force_export_paid_status=True)._integration_paid_order_hook()

        return None

    def _integration_paid_order_hook(self):
        self.ensure_one()
        if not self.integration_id.run_action_on_so_invoice_status:
            return None

        force_export_paid_status = self.env.context.get('force_export_paid_status')
        action_after_paid = self.order_is_fully_paid or force_export_paid_status

        if self.order_is_invoiced and action_after_paid:

            # 1. A case when the paid-order-hook was called by force from validate-invoice-order-hook method
            if force_export_paid_status:
                return self._perform_method_by_name(f'_{self.type_api}_paid_order')

            if self.payment_method_id:
                payment_method_external = self.payment_method_id.to_external_record(self.integration_id)

                # 2. A case when the paid-order-hook already was called on the validate-invoice-order-hook method
                if payment_method_external.send_when_invoice_is_validated:
                    return None

            # 3. Just a common case when the run_action_on_so_invoice_status property is True
            return self._perform_method_by_name(f'_{self.type_api}_paid_order')

        return None

    def order_export_tracking(self):
        self.ensure_one()
        # only send for Done pickings that were not exported yet
        # and if this is final Outgoing picking OR dropship picking
        if self.env.context.get('skip_dispatch_to_external'):
            return False

        integration = self.integration_id
        if not integration:
            return False

        if not integration.is_order_tracking_export_enabled:
            return False

        pickings = self.picking_ids._filter_pickings()

        if integration.is_carrier_tracking_required():
            pickings = pickings.filtered('carrier_tracking_ref')

        if not pickings:
            return False

        job_kwargs = self._job_kwargs_export_tracking(pickings)

        job = integration \
            .with_context(company_id=integration.company_id.id) \
            .with_delay(**job_kwargs) \
            .export_tracking(pickings)

        self.job_log(job)

        return job

    def action_refresh_data_from_external(self, data=None):
        """
        Debug action (helper) for fetching external parameters handled by the
        `_adjust_integration_external_data` and `_apply_values_from_external` methods.
        """
        for rec in self.filtered(lambda x: x.external_order_name):

            vals = rec.with_context(skip_dispatch_to_external=True) \
                ._adjust_integration_external_data(data or {})

            rec._apply_values_from_external(vals)

    def _prepare_vals_for_sale_order_status(self):
        return {
            'status': self.sub_status_id.to_external(self.integration_id),
            'delivery_date': self.get_max_delivery_date(),
        }

    def _adjust_integration_external_data(self, external_data: dict) -> dict:
        """
        Hook method for redefining.
        Invoked after receiving an order-webhook in order to adjust received data.
        """
        return external_data

    def _apply_values_from_external(self, external_data: dict) -> dict:
        """
        Hook method for redefining.
        Invoked after creating an order from input-file and after receiving an order-webhook.
        """
        vals = dict()

        # 1. Update Order Status
        if external_data.get('integration_workflow_states'):
            status_code = external_data['integration_workflow_states'][0]

            sub_status = self.integration_id._get_order_sub_status(status_code)

            vals['sub_status_id'] = sub_status.id

        # 2. Update Order Transactions
        if external_data.get('payment_transactions'):
            Transaction = self.env['external.order.transaction'] \
                .with_context(integration_id=self.integration_id.id)

            txns = []
            for txn_data in external_data['payment_transactions']:
                txn = Transaction._get_or_create_from_external(txn_data)
                txns.append((4, txn.id, 0))

            vals['external_payment_ids'] = txns

        if vals:
            self.with_context(skip_dispatch_to_external=True).write(vals)

        # -- Post actions -- TODO: this actions have to be process by workflow tasks (integration.workflow.pipeline)
        if self.env.context.get('skip_integration_order_post_action'):
            return external_data

        if self.order_is_confirmed:
            # 4.1 Apply fulfillments
            self._integration_apply_external_fulfillments()

            # 4.2 Apply payments
            if self.is_order_invoices_posted and not self.order_is_fully_paid:
                self._integration_apply_external_payments()

        return external_data

    def get_max_delivery_date(self):
        self.ensure_one()
        delivery_date = False

        if self.check_is_order_shipped():
            pickings_done = self.picking_ids.filtered(lambda p: p.state == 'done')
            if pickings_done:
                last_delivery_date = max(pickings_done.mapped('date_done'))
                delivery_date = last_delivery_date.strftime(DATETIME_FORMAT)

        return delivery_date

    def _build_and_run_integration_workflow(self, workflow_states, payment_method_code):
        _logger.info('%s: create new / update existing Integration pipeline: %s', self.integration_id.name, self.name)

        self.ensure_one()
        pipeline = self.integration_pipeline

        if pipeline:
            pipeline._update_pipeline(workflow_states, payment_method_code)
        else:
            _task_list, vals = self._build_task_list_and_vals(workflow_states, payment_method_code)
            next_step_task_list = _task_list and (_task_list[1:] + [(False, False)])

            pipeline_task_ids = [
                (0, 0, {
                    'current_step_method': x[0],
                    'next_step_method': y[0],
                    'state': [SKIP, TO_DO][x[1]],
                })
                for x, y in zip(_task_list, next_step_task_list)
            ]
            pipeline_vals = {
                **vals,
                'order_id': self.id,
                'input_file_id': self.input_file_id,
                'pipeline_task_ids': pipeline_task_ids,
            }
            pipeline = self.env['integration.workflow.pipeline'].create(pipeline_vals)
            _logger.info('New integration pipeline for %s was created: %s', self.name, str(pipeline.loginfo))

        if pipeline.has_tasks_to_process:
            _logger.info('%s: integration pipeline ready to run.', self.name)
            pipeline._mark_input_to_process()

            job_kwargs = self._job_kwargs_run_integration_workflow()
            job = pipeline\
                .with_context(company_id=self.company_id.id) \
                .with_delay(**job_kwargs) \
                .trigger_pipeline()

            pipeline.job_log(job)
        else:
            _logger.info('%s: integration pipeline has no active tasks.', self.name)
            pipeline._mark_input_as_done()

        return pipeline

    def _job_kwargs_run_integration_workflow(self, task=None, priority=9):
        key = f'{self.integration_id.id}-{self}-{self.integration_pipeline.input_file_id.name}'
        if task:
            key = f'{task}-{key}'

        return {
            'priority': priority,
            'identity_key': f'integration_workflow_pipeline-{key}',
            'channel': self.sudo().env.ref('integration.channel_sale_order').complete_name,
            'description': f'{self.integration_id.name}: Order № "{self.display_name}" >> RUN INTEGRATION WORKFLOW',
        }

    def _job_kwargs_export_tracking(self, pickings):
        return {
            'priority': 10,
            'identity_key': f'order_export_tracking-{self.integration_id.id}-{self.id}-{pickings.ids}',
            'description': (
                f'{self.integration_id.name}: Export tracking '
                f'[{self.name}] ({self.id}). Pickings [{", ".join(pickings.mapped("name"))}]'
            ),
        }

    def _job_kwargs_export_sale_order_status(self, order):
        return {
            'priority': 10,
            'identity_key': f'export_sale_order_status-{self.integration_id.id}-{order.id}-{order.sub_status_id.id}',
            'description': (
                f'{self.integration_id.name}: Export Sale Order Status '
                f'[{order.name}] ({order.id}). Status: {order.sub_status_id.name}'
            ),
        }

    def _build_task_list_and_vals(self, workflow_states, payment_method_code):
        """
        Builds the list of workflow tasks and corresponding pipeline values for an order.

        :param workflow_states: list of external order status codes.
        :param payment_method_code: external payment method code.
        :return: a tuple containing the updated task list and pipeline values.
        """
        integration = self.integration_id
        payment = payment_method_code
        state_list = workflow_states
        PaymentExternal = self.env['integration.sale.order.payment.method.external']
        SubStatusExternal = self.env['integration.sale.order.sub.status.external']

        if not all(state_list):
            raise ApiImportError(_(
                'Order substatus or payment method not found in the parsed data.\n\n'
                'Please check the order data: workflow_states=%s, payment_method_code=%s'
            ) % (state_list, payment))

        payment_external = PaymentExternal.get_external_by_code(integration, payment, raise_error=False)

        if payment and not payment_external:
            raise ApiImportError(_(
                'External payment method with the code "%s" not found.\n\n'
                'Please ensure that payment methods were imported from e-commerce system.'
            ) % payment)

        # Process the substatus workflow states
        sub_states_recordset = SubStatusExternal
        for state in state_list:
            sub_state_external = SubStatusExternal.get_external_by_code(integration, state, raise_error=False)

            if not sub_state_external:
                raise ApiImportError(_(
                    'External order substatus with the code "%s" not found.\n\n'
                    'Please ensure that substatuses were imported from the e-commerce system.'
                ) % state)

            sub_states_recordset |= sub_state_external

        pipeline_vals = {
            'payment_method_external_id': payment_external.id,
            'sub_state_external_ids': [(6, 0, sub_states_recordset.ids)],
        }

        task_list = list()  # Summing of the all possible `sub-status` tasks
        for sub_state in sub_states_recordset:
            sub_task_list = sub_state.retrieve_active_workflow_tasks()
            task_list.extend(sub_task_list)

        task_dict = defaultdict(list)  # Convert tasks to a `dict` with values as `task-enable list`
        for task_name, task_enable, task_priority in task_list:
            task_dict[(task_name, task_priority)].append(task_enable)

        task_list.clear()  # Convert `task-enable list` to a `bool` value
        for (task_name, task_priority), task_enable_list in task_dict.items():
            task_list.append((task_name, any(task_enable_list), task_priority))

        task_list.sort(key=lambda x: x[2])  # Sort by `task priority`

        task_list_updated = reset_next_value_if_not_previous(task_list)

        # [('task name', 'task enable'), ...], pipeline vals
        return task_list_updated, pipeline_vals

    def _create_invoices(self, grouped=False, final=False, date=None):
        if self.env.context.get('from_integration_workflow'):
            for order in self:
                for line in order.order_line:
                    if line.qty_delivered_method == 'manual' and not line.qty_delivered:
                        line.write({'qty_delivered': line.product_uom_qty})

        return super(SaleOrder, self)._create_invoices(grouped=grouped, final=final, date=date)

    def _prepare_invoice(self):
        invoice_vals = super(SaleOrder, self)._prepare_invoice()

        if invoice_vals['move_type'] in ('out_invoice', 'out_refund'):
            invoice_vals['integration_id'] = self.integration_id.id
            invoice_vals['external_payment_method_id'] = self.payment_method_id.id

        if self.env.context.get('from_integration_workflow'):
            pipeline = self.integration_pipeline

            invoice_date = fields.Date.context_today(self, self.date_order)
            invoice_vals['invoice_date'] = invoice_date

            # Ensure an invoice journal is defined, otherwise raise an error
            if not pipeline.invoice_journal_id:
                raise UserError(_(
                    'No Invoice Journal defined for the "Create Invoice" method.\n\n'
                    'Please go to "E-Commerce Integrations → Configuration → Auto-Workflow → Order Statuses"'
                    'and define an "Invoice Journal" for the integration "%s" and substatus "%s".'
                ) % (self.integration_id.name, ', '.join(pipeline.sub_state_external_ids.mapped('code'))))

            invoice_vals['journal_id'] = pipeline.invoice_journal_id.id

        return invoice_vals

    def _integration_validate_order(self):
        _logger.info('Run integration auto-workflow validate_order: %s', self)

        self.ensure_one()
        args = self._get_description_id_name()

        if self.order_is_cancelled:
            return False, _('%s (id=%s) [%s]: order was already cancelled.') % args

        if self.order_is_confirmed:
            return True, _('%s (id=%s) [%s]: already confirmed.') % args

        self.action_confirm()

        if self.order_is_confirmed:
            return True, _('%s (id=%s) [%s]: confirmed successfully.') % args

        return False, _('%s (id=%s) [%s]: order confirmation error.') % args

    def _integration_validate_picking(self):
        _logger.info('Run integration auto-workflow validate_picking: %s', self)

        self.ensure_one()
        args = self._get_description_id_name()

        pickings = self.picking_ids.filtered(lambda x: x.state not in ('done', 'cancel'))
        if not pickings:
            return True, _('%s (id=%s) [%s]: there are no pickings awaiting validation.') % args

        result, message = pickings._auto_validate_picking()

        return result, '%s (id=%s) [%s]: %s' % (*args, message)

    def _integration_create_invoice(self):  # TODO: what should we do if nothing to invoice
        _logger.info('Run integration auto-workflow create_invoice: %s', self)

        self.ensure_one()
        args = self._get_description_id_name()

        if self.order_is_invoiced:
            return True, _('%s (id=%s) [%s]: already invoiced.') % args

        self.with_context(from_integration_workflow=True)._create_invoices(final=True)

        if self.order_is_invoiced:
            return True, _('%s (id=%s) [%s]: created invoices successfully.') % args

        return False, _('%s (id=%s) [%s]: invoices creation error.') % args

    def _integration_validate_invoice(self):
        _logger.info('Run integration auto-workflow validate_invoice: %s', self)

        self.ensure_one()
        args = self._get_description_id_name()

        invoices = self.actual_invoice_ids.filtered(lambda x: x.state == 'draft')
        if not invoices:
            return True, _('%s (id=%s) [%s]: there are no invoices awaiting validation.') % args

        invoices.with_company(self.company_id).action_post()

        if self.is_order_invoices_posted:
            return True, _('%s (id=%s) [%s]: validated invoices successfully.') % args

        return False, _('%s (id=%s) [%s]: invoices validation failed.') % args

    def _integration_send_invoice(self):
        _logger.info('Run integration auto-workflow send_invoice: %s', self)
        self.ensure_one()

        invoices = self.invoice_ids.filtered(lambda x: x.invoice_is_posted and x.partner_id.email)

        if not invoices:
            _logger.warning('[Integration]: No valid invoices found for order %s (id=%s).', self.name, self.id)
            return False, _('%s (id=%s) [%s]: no valid invoices to send.') % self._get_description_id_name()

        errors = []
        for invoice in invoices:
            action = invoice.action_invoice_sent()

            if action.get('res_model') != 'account.move.send.wizard':
                msg = f'Invoice {invoice.name}: email layout or template is not properly configured.'
                _logger.error('[Integration]: %s', msg)
                errors.append(msg)
                continue

            action_context = action['context']

            wizard = self.env['account.move.send.wizard'] \
                .with_context(**action_context) \
                .create({'sending_methods': ['email']})

            try:
                wizard.action_send_and_print()
            except Exception as e:
                _logger.error('[Integration]: Failed to send invoice %s: %s', invoice.name, e)
                errors.append(f'Failed to send invoice {invoice.name}: {str(e)}')

            if invoice.is_move_sent:
                _logger.info('[Integration]: Invoice %s sent successfully.', invoice.name)
            else:
                _logger.warning('[Integration]: Wizard did not confirm sending for invoice %s.', invoice.name)
                errors.append(f'Wizard did not confirm sending for invoice {invoice.name}')

        if not errors:
            return True, _('Invoices sent')

        _logger.error('[Integration]: Failed to send invoices for order %s (id=%s)', self.name, self.id)
        return False, _('Failed to send invoices: %s') % ', '.join(errors)

    def _integration_register_payment(self):
        _logger.info('Run integration auto-workflow register_payment: %s', self)

        self.ensure_one()
        args = self._get_description_id_name()

        invoices = self.actual_invoice_ids.filtered(lambda x: x.invoice_is_posted and x.invoice_to_pay)
        if not invoices:
            return True, _('%s (id=%s) [%s]: there are no invoices awaiting payment registration.') % args

        for invoice in invoices:
            self._integration_register_payment_one(invoice.id)

        if self.order_is_fully_paid:
            external_payments = self.external_payment_ids
            external_payments.filtered(lambda x: x.is_ecommerce_ok).mark_done()
            external_payments.filtered(lambda x: not x.is_done).mark_skipped()
            return True, _('%s (id=%s) [%s]: the all successfully registered.') % args

        return False, _('%s (id=%s) [%s]: not the all payments were registered.') % args

    def _integration_action_cancel(self):
        _logger.info('Run integration action_cancel: %s', self)

        self.ensure_one()
        args = self._get_description_id_name()

        if self.order_is_cancelled:
            return True, _('%s (id=%s) [%s]: order was already cancelled.') % args

        self.with_context(
            disable_cancel_warning=True,
            company_id=self.integration_id.company_id.id,
        ).action_cancel()

        if self.order_is_cancelled:
            return True, _('%s (id=%s) [%s]: order was successfully cancelled.') % args

        return False, _('%s (id=%s) [%s]: order cancellation error.') % args

    def _integration_action_cancel_no_dispatch(self):
        return self.with_context(skip_dispatch_to_external=True)._integration_action_cancel()

    def _integration_register_payment_one(self, invoice_id: int):
        invoice = self.env['account.move'].browse(invoice_id)
        if invoice.invoice_is_paid:
            return True

        journal = self.integration_pipeline.get_payment_journal_or_raise()

        wizard = self.env['account.payment.register'] \
            .with_context(
                active_ids=invoice.ids,
                active_model=invoice._name,
                default_integration_id=self.integration_id.id,
            ).create({
                'journal_id': journal.id,
            })

        payments = wizard._create_payments()

        return bool(payments)

    def _prepare_confirmation_values(self):
        res = super()._prepare_confirmation_values()

        # As mentioned in parent method, self can contain multiple records.
        # In this case we can't set the date_order for all records.
        if len(self) > 1:
            return res

        if self.integration_id:
            res.update({
                'date_order': self.date_order,
            })

        return res

    def _prepare_pdf_invoices(self):
        """
        Generate a single combined PDF file with all validated invoices and credit notes
        related to this sale order, attach it, and return a download link.

        Returns:
            tuple: (code, message, data)
                code (int): 0 = success, 1 = error
                message (str): Status message
                data (list): List with dict containing PDF filename and download link
        """
        self.ensure_one()

        success_code = 0
        error_code = 1
        message = ''
        data = []

        if self.state != 'sale':
            message = f'Order {self.display_name} is not confirmed yet.'
            return error_code, message, data

        # Get all related documents (invoices and credit notes)
        all_documents = self.actual_invoice_ids

        if not all_documents:
            if self.invoice_status != 'to invoice':
                message = 'Order %s has no invoices and hasn\'t status "to invoice".' % self.display_name
                return error_code, message, data

        # Try to find an invoice that is validated
        posted_documents = all_documents.filtered(lambda i: i.invoice_is_posted)

        if (
                self.integration_id.behavior_on_non_existing_invoice == 'return_not_exist'
                and not posted_documents
        ):
            message = 'No validated invoice was found for order %s' % self.display_name
            return error_code, message, data

        # Create invoice if it is not created yet
        if not posted_documents and self.invoice_status == 'to invoice':
            try:
                invoice_created = self._create_invoices(final=True)
                if not invoice_created:
                    message = 'Invoice creation error'
                    return error_code, message, data

            except (ValidationError, UserError) as e:
                message = e.args[0]
                return error_code, message, data

            except Exception as e:
                message = e.args[0]
                return error_code, message, data

        # Validate invoice if it is not validated yet
        try:
            invoice_validated, _ = self._integration_validate_invoice()
            if not invoice_validated:
                message = 'Invoice validation error'
                return error_code, message, data

            posted_documents = self.actual_invoice_ids.filtered(lambda i: i.invoice_is_posted)

        except (ValidationError, UserError) as e:
            message = e.args[0]
            return error_code, message, data

        except Exception as e:
            message = e.args[0]
            return error_code, message, data

        ActionsReport = self.env['ir.actions.report']
        report_template = self.integration_id.invoice_report_id

        try:
            final_pdf, __ = ActionsReport._render(report_template, posted_documents.ids)
        except (UserError, Exception) as e:
            return error_code, f'PDF generation error: {str(e)}', data

        # Create attachment with PDF
        access_token = self.env['ir.attachment']._generate_access_token()

        attachment = self.env['ir.attachment'].create({
            'name': f'document_{self.name}.pdf',
            'type': 'binary',
            'datas': base64.b64encode(final_pdf),
            'res_model': 'sale.order',
            'res_id': self.id,
            'mimetype': 'application/x-pdf',
            'access_token': access_token,
        })

        base_url = self.integration_id.get_base_url_config()

        # Get invoice numbers from all posted documents
        invoice_numbers = posted_documents.mapped('name')
        invoice_number = ', '.join(invoice_numbers) if invoice_numbers else ''

        data.append({
            'name': attachment.name,
            'link': f'{base_url}/web/content/{attachment.id}?download=True&access_token={access_token}',
            'invoice_number': invoice_number,
        })

        return success_code, 'PDF document successfully generated.', data

    def get_integration_order_name(self, integration, order_ref):
        if integration.use_odoo_so_numbering:
            return None
        if integration.order_name_ref:
            return '%s%s' % (integration.order_name_ref, order_ref)
        return order_ref

    def _get_pickings_to_handle(self):
        return self.picking_ids._filter_pickings_to_handle()

    def action_cancel_integration(self):
        self.ensure_one()

        result = self.action_cancel()

        if isinstance(result, dict):  # ir.actions.act_window
            return result

        if self.env.context.get('disable_cancel_warning'):
            return result

        if not self.integration_id.is_active or not self.integration_id.is_integration_cancel_allowed():
            return result

        wizard = self.env['sale.order.cancel'].create({
            'order_id': self.id,
        })
        wizard_ = wizard._check_integration_order_status()

        return wizard_.open_integration_cancel_view()

    def _compute_customer_repeats(
            self,
            start_date: str,
            end_date: str,
            condition: str,
            condition_params: list,
    ) -> tuple:

        total_customers_query = f"""
            SELECT COUNT(DISTINCT so.partner_id) AS total_customers
            FROM sale_order so
            WHERE {condition}
        """
        self.env.cr.execute(total_customers_query, condition_params)
        total_customers = self.env.cr.fetchone()[0] or 0
        customers_with_more_than_one_order = 0

        if total_customers > 0:
            # Find all customers who placed orders in the past (before current period)
            repeat_customers_query = f"""
                SELECT COUNT(DISTINCT so.partner_id)
                FROM sale_order so
                WHERE so.partner_id IN (
                    SELECT DISTINCT so.partner_id
                    FROM sale_order so
                    WHERE {condition}
                )
                AND so.state = 'sale'
                AND so.date_order < %s
            """
            self.env.cr.execute(repeat_customers_query, condition_params + [start_date])
            customers_with_more_than_one_order = self.env.cr.fetchone()[0] or 0

        return total_customers, customers_with_more_than_one_order

    @api.model
    def _integration_dashboard_get_sales_cards(
        self,
        start_date: str,
        end_date: str,
        integration_ids: list,
        compute_repeat_purchase_rate=True,
    ) -> dict:
        """
        Compute aggregate sales metrics (revenue, orders, AOV, repeat rate, median order value) for the given period
        and integrations, converting all amounts to a single company currency.

        Steps:
        - Validate arguments and filters.
        - Fetch all orders (amount_total, currency_id, date_order).
        - Convert each order's amount_total to company currency.
        - From these converted values:
        - sum them to get total_revenue_converted
        - count them to get number_of_orders
        - sort them to compute median_order_value
        - Compute average_order_value = total_revenue_converted / number_of_orders (if orders exist)
        - Compute total_customers and repeat_purchase_rate via separate queries
        - Return all metrics including median_order_value
        """
        condition, condition_params = _prepare_integration_dashboard_condition(start_date, end_date, integration_ids)

        company, currency, __ = self._get_dashboard_user_properties()
        date_for_conversion = fields.Date.context_today(self)

        # Fetch all orders
        orders_query = f"""
            SELECT so.amount_total, so.currency_id
            FROM sale_order so
            WHERE {condition}
        """
        self.env.cr.execute(orders_query, condition_params)
        orders_data = self.env.cr.fetchall()

        number_of_orders = len(orders_data)
        if not number_of_orders:
            return {
                'sales_revenue': 0,
                'number_of_orders': 0,
                'average_order_value': 0,
                'repeat_purchase_rate': 0,
                'median_order_value': 0,
                'currency_symbol': currency.symbol,
            }

        converted_values = []
        total_revenue_converted = 0.0
        for (amt, cur_id) in orders_data:
            order_currency = self.env['res.currency'].browse(cur_id)
            if cur_id != currency.id:
                converted_amt = order_currency._convert(amt, currency, company, date_for_conversion)
            else:
                converted_amt = amt
            converted_values.append(converted_amt)
            total_revenue_converted += converted_amt

        # Compute average_order_value
        average_order_value = total_revenue_converted / number_of_orders if number_of_orders > 0 else 0.0

        # Compute median_order_value
        converted_values.sort()
        if number_of_orders % 2 == 1:
            median_order_value = converted_values[number_of_orders // 2]
        else:
            mid = number_of_orders // 2
            median_order_value = (converted_values[mid - 1] + converted_values[mid]) / 2

        repeat_purchase_rate = 0
        if compute_repeat_purchase_rate:
            total_customers, customers_with_more_than_one_order = self._compute_customer_repeats(
                start_date,
                end_date,
                condition,
                condition_params,
            )

            if total_customers:
                repeat_purchase_rate = (customers_with_more_than_one_order / total_customers) * 100

        return {
            'sales_revenue': int(total_revenue_converted),
            'number_of_orders': number_of_orders,
            'average_order_value': int(average_order_value),
            'repeat_purchase_rate': int(repeat_purchase_rate),
            'median_order_value': int(median_order_value),
            'currency_symbol': currency.symbol,
        }

    @api.model
    def _integration_dashboard_get_sales_data(
        self,
        start_date: str,
        end_date: str,
        integration_ids: list,
    ) -> dict:
        """
        Compute daily sales revenue for the given period and integrations, converting all amounts to a single currency.
        Returns a dict with 'labels' (dates) and 'values' (converted revenue per day).
        """
        condition, condition_params = _prepare_integration_dashboard_condition(start_date, end_date, integration_ids)

        company, currency, __ = self._get_dashboard_user_properties()
        date_for_conversion = fields.Date.context_today(self)

        # Group by day (YYYY-MM-DD) and currency_id
        # We use TO_CHAR to extract the day in a 'YYYY-MM-DD' string format
        query = f"""
            SELECT
                TO_CHAR(so.date_order, 'YYYY-MM-DD') AS order_day,
                so.currency_id,
                COALESCE(SUM(so.amount_total), 0) AS total_revenue
            FROM sale_order so
            WHERE {condition}
            GROUP BY order_day, so.currency_id
            ORDER BY order_day
        """

        self.env.cr.execute(query, condition_params)
        results = self.env.cr.fetchall()

        # We'll accumulate revenue per day in company currency
        # Create a dict: { 'YYYY-MM-DD': {currency_id: amount, ...}, ... }
        day_currency_map = {}
        for (order_day, cur_id, total_rev) in results:
            if order_day not in day_currency_map:
                day_currency_map[order_day] = {}
            day_currency_map[order_day][cur_id] = total_rev

        # Convert and sum per day
        final_day_sums = {}
        for day, cur_data in day_currency_map.items():
            day_sum = 0.0
            for cur_id, rev in cur_data.items():
                if cur_id != currency.id:
                    order_currency = self.env['res.currency'].browse(cur_id)
                    converted_amount = order_currency._convert(rev, currency, company, date_for_conversion)
                else:
                    converted_amount = rev
                day_sum += converted_amount

            final_day_sums[day] = day_sum

        # Build labels and values
        # final_day_sums keys are sorted by day due to ORDER BY in query
        # If needed, we can ensure sorting by converting keys to datetime and sorting, but ORDER BY day should suffice.
        labels, values = [], []
        for day in sorted(final_day_sums.keys()):
            labels.append(day)
            values.append(round(final_day_sums[day], 2))

        if not labels:
            return {}

        return {
            'labels': labels,
            'values': values,
            'currency_symbol': currency.symbol,
        }

    @api.model
    def _integration_dashboard_get_order_value_distribution(
        self,
        start_date: str,
        end_date: str,
        integration_ids: list,
    ) -> dict:
        """
        Compute the distribution of orders into three dynamic buckets based on amount_total,
        considering multiple currencies. The intervals are determined based on the data density
        and rounded up to the nearest hundred.

        Returns:
            dict: {
                'labels': [str, str, str],  # Bucket labels with currency symbol
                'values': [int, int, int],  # Counts of orders in each bucket
                'currency_symbol': str,      # Currency symbol used in labels
            }
        """
        condition, condition_params = _prepare_integration_dashboard_condition(start_date, end_date, integration_ids)

        company, currency, __ = self._get_dashboard_user_properties()
        date_for_conversion = fields.Date.context_today(self)

        # Fetch all orders: amount_total, currency_id
        orders_query = f"""
            SELECT so.amount_total, so.currency_id
            FROM sale_order so
            WHERE {condition}
        """
        self.env.cr.execute(orders_query, condition_params)
        orders_data = self.env.cr.fetchall()

        if not orders_data:
            return {}

        converted_amounts = []
        for (amt, cur_id) in orders_data:
            order_currency = self.env['res.currency'].browse(cur_id)

            converted_amt = amt
            if cur_id != currency.id:
                converted_amt = order_currency._convert(amt, currency, company, date_for_conversion)

            converted_amounts.append(converted_amt)

        # Determine min and max
        min_val = min(converted_amounts)
        max_val = max(converted_amounts)

        if min_val == max_val:
            # All orders have the same converted amount
            total_orders = len(converted_amounts)
            labels = [
                f'{math.ceil(min_val / 100) * 100} (all orders)',
                'No other range',
                'No other range',
            ]
            return {
                'labels': labels,
                'values': [total_orders, 0, 0],
                'currency_symbol': currency.symbol,
            }

        # Sort the converted amounts for quantile calculation
        sorted_amounts = sorted(converted_amounts)
        n = len(sorted_amounts)

        # Determine the 1/3 and 2/3 quantile positions
        pos1 = math.ceil(n / 3)
        pos2 = math.ceil(2 * n / 3)

        raw_bound1 = sorted_amounts[pos1 - 1]  # zero-based index
        raw_bound2 = sorted_amounts[pos2 - 1]

        # Function to round up to the nearest hundred
        def round_up_to_hundred(x):
            return math.ceil(x / 100) * 100

        # Round the boundaries up to the nearest hundred
        bound1 = round_up_to_hundred(raw_bound1)
        bound2 = round_up_to_hundred(raw_bound2)

        # Define the three intervals:
        # 1. [min_val, bound1]
        # 2. (bound1, bound2]
        # 3. (bound2, max_val]
        bucket_1 = sum(1 for v in converted_amounts if min_val <= v <= bound1)
        bucket_2 = sum(1 for v in converted_amounts if bound1 < v <= bound2)
        bucket_3 = sum(1 for v in converted_amounts if bound2 < v <= max_val)

        labels = [
            f'{int(math.floor(min_val))} to {int(bound1)}, {currency.symbol}',
            f'{int(bound1 + 1)} to {int(bound2)}, {currency.symbol}',
            f'More than {int(bound2)}, {currency.symbol}'
        ]

        return {
            'labels': labels,
            'values': [bucket_1, bucket_2, bucket_3],
            'currency_symbol': currency.symbol,
        }

    @api.model
    def _integration_dashboard_get_products_data(
        self,
        start_date: str,
        end_date: str,
        integration_ids: list,
    ) -> list:
        """
        Compute the top 10 products by total revenue for the given period and integrations,
        considering multiple currencies. Amounts are converted into the company's currency before sorting.

        Steps:
        - Validate arguments and apply filters.
        - Query product sales grouped by (product_id, product_name, default_code, currency_id).
        - Convert each currency sum once into company currency.
        - Aggregate revenue by product (in case multiple currencies appear for the same product).
        - Determine total_revenue_all from these converted sums.
        - Compute percentage and return top 10 products by revenue.
        """
        condition, condition_params = _prepare_integration_dashboard_condition(start_date, end_date, integration_ids)

        company, currency, lang = self._get_dashboard_user_properties()
        date_for_conversion = fields.Date.context_today(self)

        # First, group by product and currency
        products_query = f"""
            SELECT
                pp.id AS product_id,
                pt.name->>'{lang}' AS product_name,
                pp.default_code,
                so.currency_id,
                SUM(sol.product_uom_qty) AS units_sold,
                SUM(sol.product_uom_qty * sol.price_unit) AS total_revenue
            FROM sale_order_line sol
            JOIN sale_order so ON so.id = sol.order_id
            JOIN product_product pp ON pp.id = sol.product_id
            JOIN product_template pt ON pt.id = pp.product_tmpl_id
            WHERE {condition}
            GROUP BY pt.name, pp.default_code, pp.id, so.currency_id
            ORDER BY SUM(sol.product_uom_qty * sol.price_unit) DESC
        """

        self.env.cr.execute(products_query, condition_params)
        product_results = self.env.cr.fetchall()

        if not product_results:
            return []

        # Accumulate revenue by product in company currency
        product_map = {}
        for (product_id, product_name, default_code, cur_id, units_sold, total_revenue) in product_results:
            if product_id not in product_map:
                product_map[product_id] = {
                    'id': product_id,
                    'name': product_name,
                    'default_code': default_code,
                    'units_sold': 0.0,
                    'revenue_by_currency': {}
                }
            product_map[product_id]['units_sold'] += units_sold
            if cur_id not in product_map[product_id]['revenue_by_currency']:
                product_map[product_id]['revenue_by_currency'][cur_id] = 0.0
            product_map[product_id]['revenue_by_currency'][cur_id] += float(total_revenue)

        # Convert revenues per product
        for product_data in product_map.values():
            total_converted = 0.0
            for cur_id, rev in product_data['revenue_by_currency'].items():
                if cur_id != currency.id:
                    order_currency = self.env['res.currency'].browse(cur_id)
                    converted_amount = order_currency._convert(rev, currency, company, date_for_conversion)
                else:
                    converted_amount = rev
                total_converted += converted_amount
            product_data['total_revenue_converted'] = total_converted

        # Compute total_revenue_all from converted values
        total_revenue_all = sum(p['total_revenue_converted'] for p in product_map.values())

        if total_revenue_all == 0:
            return []

        # Compute percent_total and prepare final list
        products_list = []
        for p in product_map.values():
            percent_total = 0.0
            if total_revenue_all > 0:
                percent_total = (p['total_revenue_converted'] / total_revenue_all) * 100

            products_list.append({
                'id': p['id'],
                'name': p['name'],
                'default_code': p['default_code'],
                'units_sold': int(p['units_sold']),
                'total_revenue': round(p['total_revenue_converted'], 2),
                'percent_total': round(percent_total, 2),
                'currency_symbol': currency.symbol,
            })

        # Sort by revenue and take top 10
        products_list.sort(key=lambda x: x['total_revenue'], reverse=True)
        products_list = products_list[:10]

        return products_list

    @api.model
    def _integration_dashboard_get_store_performance(
        self,
        start_date: str,
        end_date: str,
        integration_ids: list,
    ) -> list:
        """
        Returns store performance data considering multiple currencies.
        For each store, calculates the total revenue, number of orders, average order value (AOV),
        median order value, and includes the currency symbol.
        """
        result = []
        for integration_id in integration_ids:
            res = self._integration_dashboard_get_sales_cards(
                start_date,
                end_date,
                [integration_id],
                compute_repeat_purchase_rate=False,
            )
            res['name'] = self.env['sale.integration'].browse(integration_id).name
            result.append(res)

        return result

    @api.model
    def _integration_dashboard_get_top_countries(
        self,
        start_date: str,
        end_date: str,
        integration_ids: list,
        limit: int = 10,
    ) -> list:
        """
        Returns top countries by total revenue considering multiple currencies.
        Now we determine the country from the billing address (partner_invoice_id)
        instead of the main partner_id.

        Steps:
        - Compute total revenue per currency for all orders.
        - Compute revenue by (country, currency_id) using partner_invoice_id.
        - Convert each currency block once, sum per country.
        - Calculate percentage = (country_revenue / total_revenue_all) * 100.
        - Sort by percent and take top N.
        """
        condition, condition_params = _prepare_integration_dashboard_condition(start_date, end_date, integration_ids)

        company, currency, lang = self._get_dashboard_user_properties()
        date_for_conversion = fields.Date.context_today(self)

        # 1. Compute total revenue by currency
        total_revenue_by_currency_query = f"""
            SELECT so.currency_id, COALESCE(SUM(so.amount_total), 0) AS total_revenue
            FROM sale_order so
            WHERE {condition}
            GROUP BY so.currency_id
        """
        self.env.cr.execute(total_revenue_by_currency_query, condition_params)
        total_by_currency_res = self.env.cr.fetchall()

        total_revenue_all = 0
        for (cur_id, cur_rev) in total_by_currency_res:
            if cur_id != currency.id:
                order_currency = self.env['res.currency'].browse(cur_id)
                converted_amount = order_currency._convert(cur_rev, currency, company, date_for_conversion)
            else:
                converted_amount = cur_rev
            total_revenue_all += converted_amount

        if not total_revenue_all:
            return []

        # 2. Compute revenue by country and currency using partner_invoice_id
        # You may multiply `limit` by 5 here to ensure that you fetch enough rows from the database to properly
        # determine the top N countries after currency conversion and aggregation. Since the query groups by both
        # `country_name` and `currency_id`, a single country might appear multiple times with different currencies.
        # Retrieving only `LIMIT {limit}` rows could truncate some currency entries for that country and lead to an
        # incomplete total. By using a higher limit (e.g., `limit * 5`), you collect more potential entries per country.
        # After converting and summing their revenues, you can then apply the final sorting and select the top N
        # countries in Python, ensuring accuracy even with multiple currency lines per country.
        query_countries = f"""
            SELECT
                (rc.name->>'{lang}') AS country_name,
                so.currency_id,
                SUM(so.amount_total) AS total_revenue
            FROM sale_order so
            JOIN res_partner rp ON rp.id = so.partner_invoice_id
            JOIN res_country rc ON rc.id = rp.country_id
            WHERE {condition}
            GROUP BY rc.name, so.currency_id
            ORDER BY SUM(so.amount_total) DESC
            LIMIT {limit * 5}
        """

        self.env.cr.execute(query_countries, condition_params)
        countries_result = self.env.cr.fetchall()

        # Accumulate revenue per country
        country_map = {}
        for (country_name, cur_id, rev) in countries_result:
            if country_name not in country_map:
                country_map[country_name] = {}
            if cur_id not in country_map[country_name]:
                country_map[country_name][cur_id] = 0.0
            country_map[country_name][cur_id] += float(rev)

        # Convert and sum per country
        countries_data = []
        for country_name, currency_data in country_map.items():
            country_total_converted = 0.0
            for cur_id, rev in currency_data.items():
                if cur_id != currency.id:
                    order_currency = self.env['res.currency'].browse(cur_id)
                    converted_amount = order_currency._convert(rev, currency, company, date_for_conversion)
                else:
                    converted_amount = rev
                country_total_converted += converted_amount

            percent = (country_total_converted / total_revenue_all) * 100 if total_revenue_all > 0 else 0.0
            countries_data.append({
                'name': country_name,
                'percent': round(percent, 2)
            })

        # Sort by percent descending and take top N
        countries_data.sort(key=lambda x: x['percent'], reverse=True)
        countries_data = countries_data[:limit]

        return countries_data

    @api.model
    def _integration_dashboard_get_new_vs_returning_customers(
        self,
        start_date: str,
        end_date: str,
        integration_ids: list,
    ) -> dict:
        """
        Returns data for a "New vs Returning Customers" (%) horizontal bar chart:
        {
            'labels': ['New Customers', 'Returning Customers'],
            'values': [<float new_customers_count>, <float returning_customers_count>]
        }
        """
        condition, condition_params = _prepare_integration_dashboard_condition(start_date, end_date, integration_ids)

        total_customers, customers_with_more_than_one_order = self._compute_customer_repeats(
            start_date,
            end_date,
            condition,
            condition_params,
        )

        new_customers_value, returning_customers_value = 0, 0

        if total_customers:
            new_customers_value = 100 * (total_customers - customers_with_more_than_one_order) / total_customers
            returning_customers_value = 100 * customers_with_more_than_one_order / total_customers

        return {
            'labels': ['New Customers', 'Returning Customers'],
            'values': [round(new_customers_value, 2), round(returning_customers_value, 2)],
        }

    def _get_dashboard_user_properties(self):
        user_id = self.env.context.get('uid') or SUPERUSER_ID
        user = self.sudo().env['res.users'].browse(user_id)

        company = user.company_id
        currency = company.currency_id or self.env.ref('base.USD')

        return company, currency, user.lang or 'en_US'

    def action_confirm(self):
        """
        Override method.
        """
        res = super(SaleOrder, self).action_confirm()

        self._integration_post_order_confirm()

        return res

    def _integration_post_order_confirm(self) -> bool:
        """
        Post-processing after order confirmation.
        """
        if not self.integration_id or not self.related_input_files:
            return None

        order_data = json.loads(self.related_input_files.raw_data)

        # Processing external field mapping for a picking (only active mappings)
        values = {}

        mappings = self.integration_id.external_order_field_mapping_ids.filtered(
            lambda m: m.active and m.odoo_picking_field_id
        )

        for mapping in mappings:
            field_name = mapping.odoo_picking_field_id.name
            value = mapping.calculate_order_import_value(order_data, raise_error=False)

            if value is not None:
                values[field_name] = value

        if values:
            self.picking_ids.write(values)

        # Validate external fulfillments if the integration supports it
        self._integration_apply_external_fulfillments()

        return True

    def _integration_apply_external_fulfillments(self):
        self.ensure_one()

        integration = self.integration_id
        if integration and integration.apply_external_fulfillments:
            if not (integration.is_integration_shopify or integration.is_integration_magento_two):
                _logger.warning(
                    _('External fulfillments are not not supported for this integration: %s (%s)')
                    % (integration.name, integration.type_api)
                )
                return

            for record in self.external_fulfillment_ids.filtered(lambda x: x.is_ecommerce_ok and not x.is_done):
                record.validate()

    def _integration_apply_external_payments(self):
        self.ensure_one()

        integration = self.integration_id
        if integration and integration.apply_external_payments:
            payments = self.external_payment_ids.filtered(lambda x: x.is_ecommerce_ok and not x.is_done)

            if payments:
                self.external_payment_ids._raise_if_refund_found()

                for payment in payments:
                    payment.validate()

    def action_open_order_in_external_system(self):
        """
        Open the order in the external system.
        """
        if not self.integration_id:
            return

        return self.related_input_files.action_open_store_order()
