# See LICENSE file for full copyright and licensing details.

import logging
import traceback

from psycopg2 import OperationalError

from odoo import api, models, fields, _

from ...exceptions import ErrorStore as es
from ...tools import raise_requeue_job_on_concurrent_update


_logger = logging.getLogger(__name__)


SKIP = 'skip'
TO_DO = 'todo'
DONE = 'done'
FAILED = 'failed'
IN_PROCESS = 'in_process'

INVOICE_DATE_SOURCE_ORDER = 'order_date'
INVOICE_DATE_SOURCE_CREATION = 'invoice_creation_date'

ALERT_NOT_CONFIGURED = 'not_configured'
ALERT_SUCCEED = 'succeed'
ALERT_FAILED = 'failed'
ALERT_PROCESSING = 'processing'

STATUS_CANCELLED = 'cancelled'
STATUS_FAILED = 'failed'
STATUS_RUNNING = 'running'
STATUS_SKIPPED = 'skipped'
STATUS_DONE = 'done'
STATUS_NONE = 'none'

PIPELINE_STATE = [
    (SKIP, 'Skipped'),
    (TO_DO, 'Waiting'),
    (IN_PROCESS, 'In Process'),
    (FAILED, 'Failed'),
    (DONE, 'Done'),
]

# Each step lists the steps that must succeed before it can run.
# IMPORTANT: insertion order is ALSO the execution order
WORKFLOW_TASK_DEPENDENCIES = {
    'validate_order': [],
    'apply_advance_payment': ['validate_order'],
    'validate_picking': ['validate_order'],
    'create_invoice': ['validate_order'],
    'validate_invoice': ['create_invoice'],
    'send_invoice': ['validate_invoice'],
    'register_payment': ['validate_invoice'],
}


class IntegrationWorkflowPipelineLine(models.Model):
    _name = 'integration.workflow.pipeline.line'
    _description = 'Integration Workflow Pipeline Line'

    name = fields.Char(
        string='Name',
        compute='_compute_name',
    )
    state = fields.Selection(
        selection=PIPELINE_STATE,
        string='State',
        default=SKIP,
    )
    current_step_method = fields.Char(
        string='Current Step',
        required=True,
    )
    next_step_method = fields.Char(
        string='Next Step',
    )
    order_id = fields.Many2one(
        comodel_name='sale.order',
        related='pipeline_id.order_id',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        related='order_id.company_id',
    )
    integration_id = fields.Many2one(
        string='E-Commerce Store',
        comodel_name='sale.integration',
        related='order_id.integration_id',
    )
    pipeline_id = fields.Many2one(
        comodel_name='integration.workflow.pipeline',
        string='Pipeline',
        ondelete='cascade',
        index=True,
    )
    skip_dispatch = fields.Boolean(
        related='pipeline_id.skip_dispatch',
    )
    skip_allowed = fields.Boolean(
        string='Skip Allowed',
        compute='_compute_skip_allowed',
        help='A failed step can be skipped only when no later enabled step depends on it.',
    )

    @api.depends('current_step_method')
    def _compute_name(self):
        for rec in self:
            method_name = rec.current_step_method
            try:
                value = self.env['integration.sale.order.sub.status.external']._fields[method_name].string
            except KeyError:
                value = f'Workflow Method "{method_name}"'

            rec.name = value

    @api.depends('state', 'current_step_method', 'pipeline_id.pipeline_task_ids.state')
    def _compute_skip_allowed(self):
        for rec in self:
            if rec.state != FAILED:
                rec.skip_allowed = False
                continue

            dependents = rec._get_dependent_steps()
            blocking = rec.pipeline_id.pipeline_task_ids.filtered(
                lambda x: x.current_step_method in dependents and x.state != SKIP
            )
            rec.skip_allowed = not blocking

    def _get_dependent_steps(self):
        """Return the set of steps that depend (directly or transitively) on this line's step."""
        self.ensure_one()
        dependents, stack = set(), [self.current_step_method]
        while stack:
            current = stack.pop()
            for step, required_steps in WORKFLOW_TASK_DEPENDENCIES.items():
                if current in required_steps and step not in dependents:
                    dependents.add(step)
                    stack.append(step)

        return dependents

    @property
    def is_not_done(self):
        return self.state != DONE

    @property
    def is_done(self):
        return self.state == DONE

    @property
    def is_skipped(self):
        return self.state == SKIP

    @property
    def is_processing(self):
        return self.state == IN_PROCESS

    @property
    def is_waiting(self):
        return self.state == TO_DO

    @property
    def is_failed(self):
        return self.state == FAILED

    def mark_skip(self):
        self.state = SKIP

    def mark_todo(self):
        self.state = TO_DO

    def mark_process(self):
        self.state = IN_PROCESS

    def mark_done(self):
        self.state = DONE

    def mark_failed(self):
        self.state = FAILED

    def task_force_done(self):
        self.ensure_one()

        self._validate_previous()
        self.set_task_to_done(update_logs=True)

        if not self.get_next_task():
            self.mark_input_as_done()

        return self.open_form()

    def task_force_draft(self):
        self.ensure_one()

        self.mark_todo()
        return self.open_form()

    def action_skip_step(self):
        """Skip a failed step and resume the workflow from the next step."""
        self.ensure_one()

        if self.state != FAILED:
            raise es.UserError(_('Only a failed step can be skipped.'))

        if not self.skip_allowed:
            raise es.UserError(_(
                'Step "%s" cannot be skipped because later enabled steps depend on it. '
                'Please resolve the issue and retry instead.', self.name
            ))

        self.mark_skip()
        self.update_info()
        self.call_next_step_job()
        return self.open_form()

    def update_info(self, message=False):
        if not message:
            return self.pipeline_id.clear_info()
        return self.pipeline_id.write({'current_info': message})

    def open_form(self):
        return self.pipeline_id.open_form()

    def call_next_step_job(self):
        return self.pipeline_id._call_pipeline_step(self.next_step_method)

    def get_next_task(self):
        return self.pipeline_id._find_task(self.next_step_method)

    def mark_input_as_done(self):
        return self.pipeline_id._mark_input_as_done()

    def set_task_to_done(self, update_logs=False):
        self.ensure_one()

        self.mark_done()
        self.update_info()

        if update_logs:
            self.mark_jobs_as_done()

        return True

    def run(self):
        """Manual running by button"""
        self.ensure_one()
        if self.state in (SKIP, DONE):
            raise es.UserError(_(
                'The task cannot be executed because it is inactive in the current auto-workflow. '
                'This task is in a "Skip" or "Done" state and cannot be processed further. '
                'Please verify the auto-workflow status.'
            ))

        self._validate_previous()
        self._process_current_step()
        return self.open_form()

    def action_retry_step(self):
        """Re-run a failed step with delay; the workflow continues from there."""
        self.ensure_one()
        self.mark_process()
        self.update_info()
        self.run_with_delay()
        return self.open_form()

    def _execute_order_method(self):
        """Run the current step's order method, capturing any failure.

        Returns ``(result, message)`` where ``result`` is True (done),
        None (in process) or False (failed).
        """
        self.pipeline_id.error_traceback = False
        order_method = self._retrieve_current_order_method()
        # Persist earlier pending writes before the savepoint so a rollback + cache
        # clear on failure can't discard them. We flush via self.env (valid user)
        # instead of a flushing savepoint, which flushes through transaction.default_env
        # (possibly empty user) and breaks EE computes like account.move.signing_user.
        self.env.flush_all()
        try:
            with self.env.cr.savepoint(flush=False):
                result = order_method()
                self.env.flush_all()
        except OperationalError:
            # Let @raise_requeue_job_on_concurrent_update handle it
            self.env.cr.clear()
            raise
        except Exception as exc:
            self.env.cr.clear()
            self.pipeline_id.error_traceback = traceback.format_exc()
            return False, _(
                'An error occurred while processing %(step)s: %(error)s',
                step=self.name, error=exc,
            )
        return result

    def _process_current_step(self):
        """Execute the current step and update its state. Returns the raw result."""
        self.ensure_one()

        result, message = self._execute_order_method()
        if result:
            self.set_task_to_done()
            if not self.get_next_task():
                self.mark_input_as_done()
        elif result is None:
            self.mark_process()
            self.update_info(message)
        else:
            self.mark_failed()
            self.update_info(message)

        return result

    def run_with_delay(self):
        """Automatic running by triggered `pipeline_id`"""
        self.ensure_one()
        job_kwargs = self._job_kwargs_pipeline_task()

        context = {
            'company_id': self.company_id.id,
            'job_integration_id': self.order_id.integration_id.id,
            'job_integration_job_type': 'order',
            'job_order_id': self.order_id.id,
        }
        job = self \
            .with_context(**context) \
            .with_delay(**job_kwargs) \
            ._run_and_call_next()

        return job

    def mark_jobs_as_done(self):
        jobs = self.env['queue.job'].search([
            ('integration_id', '=', self.integration_id.id),
            ('order_id', '=', self.order_id.id),
            ('state', '!=', 'done'),
        ])
        return jobs.button_done()

    def get_formview_action_log(self):
        return self.pipeline_id.get_formview_action_log()

    def _job_kwargs_pipeline_task(self):
        return {
            'priority': 9,
            'channel': self.env.ref('integration.channel_sale_order').complete_name,
            'identity_key': f'integration_pipeline_task-{self.integration_id.id}-{self}',
            'description': f'{self.integration_id.name}: Order № "{self.order_id.display_name}" >> {self.name}',
        }

    @raise_requeue_job_on_concurrent_update
    def _run_and_call_next(self, raise_error=False):
        if self.state in (SKIP, DONE):
            self.call_next_step_job()
            return _('Task was skipped.')

        result, message = self._execute_order_method()
        if result:
            self.set_task_to_done()
            self.call_next_step_job()
        elif result is None:
            self.mark_process()
            self.call_next_step_job()
        else:
            self.mark_failed()
            self.update_info(message)

        return message

    def _retrieve_current_order_method(self):
        order = self.order_id
        order = order.with_company(order.company_id)

        if self.skip_dispatch:
            order = order.with_context(skip_dispatch_to_external=True)
        return getattr(order, f'_integration_{self.current_step_method}')

    def _validate_previous(self):
        states = self.pipeline_id.pipeline_task_ids \
            .filtered(lambda x: x.id < self.id and x.state != SKIP).mapped('state')

        if states and not all(x == DONE for x in states):
            raise es.UserError(_(
                'Not all previous tasks are in the "Done" state. Please complete or fix '
                'the pending tasks before proceeding.'
            ))

    def _get_file_id_for_log(self):
        return self.order_id._get_file_id_for_log()


class IntegrationWorkflowPipeline(models.Model):
    _name = 'integration.workflow.pipeline'
    _description = 'Integration Workflow Pipeline'

    order_id = fields.Many2one(
        comodel_name='sale.order',
        string='Order',
        ondelete='cascade',
        required=True,
        index=True,
    )
    input_file_id = fields.Many2one(
        comodel_name='sale.integration.input.file',
        string='Input File',
        index=True,
    )
    sub_state_external_ids = fields.Many2many(
        comodel_name='integration.sale.order.sub.status.external',
        relation='pipeline_external_sub_state_relation',
        column1='pipeline_id',
        column2='sub_state_external_id',
        string='Store Order Status',
    )
    order_sub_status_id = fields.Many2one(
        related="order_id.sub_status_id",
        string='Store Status',
    )
    order_integration_id = fields.Many2one(
        related="order_id.integration_id",
        string="Store",
    )
    invoice_journal_id = fields.Many2one(
        comodel_name='account.journal',
        compute='_compute_invoice_journal',
        string='Invoice Journal',
    )
    invoice_date_source = fields.Selection(
        selection=[
            (INVOICE_DATE_SOURCE_ORDER, 'Order Date'),
            (INVOICE_DATE_SOURCE_CREATION, 'Invoice Creation Date'),
        ],
        compute='_compute_invoice_date_source',
        string='Default Invoice Date',
    )
    payment_method_external_id = fields.Many2one(
        comodel_name='integration.sale.order.payment.method.external',
        string='External Payment Method',
    )
    payment_journal_id = fields.Many2one(
        comodel_name='account.journal',
        related='payment_method_external_id.payment_journal_id',
    )
    pipeline_task_ids = fields.One2many(
        comodel_name='integration.workflow.pipeline.line',
        inverse_name='pipeline_id',
        string='Pipeline Tasks',
    )
    skip_dispatch = fields.Boolean(
        string='Skip Dispatch',
    )
    alert_type = fields.Char(
        compute='_compute_alert',
    )
    alert_title = fields.Char(
        string="Alert Title",
        compute='_compute_alert',
    )
    alert_body = fields.Char(
        string="Alert Body",
        compute='_compute_alert',
    )
    error_title = fields.Char(
        compute='_compute_error',
    )
    current_info = fields.Char(
        string='Info',
    )
    error_traceback = fields.Text(
        string="Full Traceback",
    )
    failed_task_skip_allowed = fields.Boolean(
        compute='_compute_failed_task_skip_allowed',
    )

    @property
    def all_tasks_done(self):
        return all((x.is_skipped or x.is_done) for x in self.pipeline_task_ids)

    @property
    def all_tasks_skipped(self):
        return all(x.is_skipped for x in self.pipeline_task_ids)

    @property
    def failed_task(self):
        return self.pipeline_task_ids.filtered(lambda x: x.state == FAILED)[:1]

    def get_invoice_date(self):
        """Resolve invoice date from ``invoice_date_source`` for this pipeline's order."""
        self.ensure_one()
        order = self.order_id
        if self.invoice_date_source == INVOICE_DATE_SOURCE_CREATION:
            return fields.Date.context_today(order)
        return fields.Date.context_today(order, order.date_order)

    @property
    def status(self):
        """Single source of truth for the pipeline lifecycle state."""
        self.ensure_one()
        if self.failed_task:
            return STATUS_FAILED
        if self.all_tasks_skipped:
            return STATUS_SKIPPED
        if self.all_tasks_done:
            return STATUS_DONE
        if not any(x.is_done or x.is_processing for x in self.pipeline_task_ids):
            return STATUS_NONE
        return STATUS_RUNNING

    @property
    def loginfo(self):
        return dict(
            self=str(self),
            order_id=self.order_id.id,
            integration_id=self.order_id.integration_id.id,
            tasks=self._tasks_info(),
        )

    def _compute_invoice_journal(self):
        for rec in self:
            invoice_journals = rec.sub_state_external_ids\
                .mapped('invoice_journal_id')
            rec.invoice_journal_id = invoice_journals[:1].id

    @api.depends('sub_state_external_ids.invoice_date_source')
    def _compute_invoice_date_source(self):
        for rec in self:
            sources = rec.sub_state_external_ids.mapped('invoice_date_source')
            rec.invoice_date_source = sources[0] if sources else INVOICE_DATE_SOURCE_ORDER

    @api.depends('pipeline_task_ids.state', 'order_sub_status_id')
    def _compute_alert(self):
        for rec in self:
            status = rec.status
            if status == STATUS_SKIPPED:
                alert_type = ALERT_NOT_CONFIGURED
                alert_title = _('No automation configured for this status')
                alert_body = _(
                    'No steps are enabled for %s — the order was imported, but no '
                    'automation actions ran. You can configure automation steps for '
                    'this status under E-Commerce Integrations → Configuration → Order Statuses.',
                    rec.order_sub_status_id.name
                )
            elif status == STATUS_DONE:
                alert_type = ALERT_SUCCEED
                alert_title = _('Automation Completed')
                alert_body = _('All steps finished successfully.')
            elif status == STATUS_FAILED:
                alert_type = ALERT_FAILED
                alert_title = _('Stopped at "%s"', rec.failed_task.name)
                alert_body = _('Step failed, the remaining steps are waiting.')
            else:
                alert_type = ALERT_PROCESSING
                alert_title = _('The automation is currently in process')
                alert_body = _('Please wait until all steps will be completed.')

            rec.alert_type = alert_type
            rec.alert_title = alert_title
            rec.alert_body = alert_body

    @api.depends('pipeline_task_ids.state')
    def _compute_error(self):
        for rec in self:
            task = rec.failed_task.name.lower() if rec.failed_task else _('complete the step above')
            rec.error_title = _('Could not %s', task)

    @api.depends('pipeline_task_ids.skip_allowed')
    def _compute_failed_task_skip_allowed(self):
        for rec in self:
            rec.failed_task_skip_allowed = bool(rec.failed_task.skip_allowed)

    def _get_file_id_for_log(self):
        return self.order_id._get_file_id_for_log()

    def manual_run(self):
        self.ensure_one()

        if not self.input_file_id:
            raise es.UserError(_(
                'This automation has no linked input file to re-run from.'
            ))

        lines_to_run = self.pipeline_task_ids.filtered(lambda t: t.is_waiting or t.is_failed)
        lines_to_run[:1].mark_process()
        lines_to_run[1:].mark_todo()
        self.update_info()

        job_kwargs = self.order_id._job_kwargs_run_integration_workflow()

        context = {
            'company_id': self.order_id.company_id.id,
            'job_integration_id': self.order_id.integration_id.id,
            'job_integration_job_type': 'order',
            'job_order_id': self.order_id.id,
        }
        self.input_file_id \
            .with_context(**context) \
            .with_delay(**job_kwargs) \
            .run_actual_pipeline(skip_dispatch=self.skip_dispatch)

        return self.open_form()

    def run_from_failed_step(self):
        return self.failed_task.action_retry_step()

    def action_skip_failed_step(self):
        return self.failed_task.action_skip_step()

    def action_open_order(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/odoo/orders/{self.order_id.id}',
            'target': 'new',
        }

    def action_open_input_file(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/odoo/eci-external-orders/{self.input_file_id.id}',
            'target': 'new',
        }

    def clear_info(self):
        self.current_info = False
        self.error_traceback = False
        return self.open_form()

    def _mark_input_as_done(self):
        self.input_file_id.action_done()

    def _mark_input_to_process(self):
        self.input_file_id.action_process()

    def trigger_pipeline(self):
        _logger.info('Running integration pipeline → %s', str(self.loginfo))
        if self.all_tasks_done:
            _logger.info('Skipping integration pipeline → %s', str(self.loginfo))
            self._mark_input_as_done()
            return _('Workflow Ended: %s') % self._tasks_info()

        task_to_run = self.pipeline_task_ids.filtered(lambda x: x.is_not_done)[:1]
        task_to_run.run_with_delay()

        self._mark_input_to_process()
        return self._tasks_info()

    def _call_pipeline_step(self, step_name):
        if self.all_tasks_done:
            self._mark_input_as_done()
            return _('Workflow Ended: %s') % self._tasks_info()

        task_to_run = self._find_task(step_name)

        if not task_to_run:
            self._mark_input_as_done()
            return _('Workflow Done: %s') % self._tasks_info()

        return task_to_run.run_with_delay()

    def _find_task(self, step_name):
        return self.pipeline_task_ids.filtered(lambda x: x.current_step_method == step_name)

    def _tasks_info(self):
        return [(x.id, x.name, x.state) for x in self.pipeline_task_ids]

    def _update_pipeline(self, workflow_states, payment_method_code):
        _logger.info('Updating integration pipeline: %s →', self.loginfo)

        task_list, pipeline_vals = self.order_id._build_task_list_and_vals(
            workflow_states, payment_method_code,
        )
        sub_state_ids = pipeline_vals['sub_state_external_ids'][0][-1]
        payment_method_external_id = pipeline_vals['payment_method_external_id']
        vals = {
            'sub_state_external_ids': [(4, x, 0) for x in sub_state_ids],
            'skip_dispatch': self.env.context.get('default_skip_dispatch', False),
        }
        if payment_method_external_id:
            vals['payment_method_external_id'] = payment_method_external_id

        self.write(vals)

        pipeline_task_ids = self.pipeline_task_ids
        for task_name, task_enable in task_list:
            task = pipeline_task_ids.filtered(
                lambda x: x.current_step_method == task_name
            )
            if task and task.is_not_done and task_enable:
                task.mark_todo()
                _logger.info('%s: integration pipeline task "%s" was marked as "TODO".', self, task_name)

        return vals

    def get_payment_journal_or_raise(self):
        self.payment_method_external_id._raise_for_missing_journal()
        return self.payment_journal_id

    def get_formview_action_log(self):
        return self.order_id.get_formview_action()

    def open_form(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Order Automation'),
            'res_model': self._name,
            'view_mode': 'form',
            'view_id': self.env.ref('integration.integration_workflow_pipeline_form_view').id,
            'res_id': self.id,
            'target': 'new',
        }
