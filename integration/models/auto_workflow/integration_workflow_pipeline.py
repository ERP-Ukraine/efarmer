# See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, models, fields, _
from odoo.exceptions import UserError, ValidationError

from ...tools import raise_requeue_job_on_concurrent_update


_logger = logging.getLogger(__name__)


SKIP = 'skip'
TO_DO = 'todo'
DONE = 'done'
FAILED = 'failed'
IN_PROCESS = 'in_process'

PIPELINE_STATE = [
    (SKIP, 'Skip'),
    (TO_DO, 'ToDo'),
    (IN_PROCESS, 'In Process'),
    (FAILED, 'Failed'),
    (DONE, 'Done'),
]


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
    )
    skip_dispatch = fields.Boolean(
        related='pipeline_id.skip_dispatch',
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

    @property
    def is_not_done(self):
        return self.state != DONE

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
            raise UserError(_(
                'The task cannot be executed because it is inactive in the current auto-workflow. '
                'This task is in a "Skip" or "Done" state and cannot be processed further. '
                'Please verify the auto-workflow status.'
            ))

        self._validate_previous()
        order_method = self._retrieve_current_order_method()
        result, message = order_method()

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

        return self.open_form()

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

    def _fail_job_manually(self, message):
        job_kwargs = self._job_kwargs_pipeline_task()
        job_kwargs['description'] = job_kwargs['description'] + ' [TRACEBACK INFO] (mark me as done)'

        context = {
            'company_id': self.company_id.id,
            'job_integration_id': self.order_id.integration_id.id,
            'job_integration_job_type': 'order',
            'job_order_id': self.order_id.id,
        }
        job = self \
            .with_context(**context) \
            .with_delay(**job_kwargs) \
            ._raise_message(message)

        return job

    def _job_kwargs_pipeline_task(self):
        return {
            'priority': 9,
            'channel': self.env.ref('integration.channel_sale_order').complete_name,
            'identity_key': f'integration_pipeline_task-{self.integration_id.id}-{self}',
            'description': f'{self.integration_id.name}: Order № "{self.order_id.display_name}" >> {self.name}',
        }

    def _raise_message(self, message):
        info = _(
            'This is an informational message. Please mark this job as '
            'done (there is no need to requeue it) and resolve all issues related to the order "%s" by '
            'clicking on the "Integration Workflow" button on the order form.'
        ) % self.order_id.name

        message_info = (
            f"""
            {message}
            {info}
            """
        )
        raise ValidationError(message_info)

    @raise_requeue_job_on_concurrent_update
    def _run_and_call_next(self, raise_error=False):
        if self.state in (SKIP, DONE):
            self.call_next_step_job()
            return _('Task was skipped.')

        order_method = self._retrieve_current_order_method()
        result, message = order_method()

        if result:
            self.set_task_to_done()
            self.call_next_step_job()
        elif result is None:
            self.mark_process()
            self.call_next_step_job()
        else:
            self.mark_failed()
            self.update_info(message)
            self._fail_job_manually(message)

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
            raise UserError(_(
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
    )
    input_file_id = fields.Many2one(
        comodel_name='sale.integration.input.file',
        string='Input File',
    )
    input_file_state = fields.Selection(
        related='input_file_id.state',
    )
    update_required = fields.Boolean(
        related='input_file_id.update_required',
        string='Order Data Update Required',
    )
    sub_state_external_ids = fields.Many2many(
        comodel_name='integration.sale.order.sub.status.external',
        relation='pipeline_external_sub_state_relation',
        column1='pipeline_id',
        column2='sub_state_external_id',
        string='Store Order Status',
    )
    invoice_journal_id = fields.Many2one(
        comodel_name='account.journal',
        compute='_compute_invoice_journal',
        string='Invoice Journal',
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
    current_info = fields.Char(
        string='Info',
    )

    @property
    def is_done(self):
        tasks = self.pipeline_task_ids.filtered(lambda x: x.state in (IN_PROCESS, FAILED))
        return not bool(tasks)

    @property
    def has_tasks_to_process(self):
        tasks = self.pipeline_task_ids.filtered(lambda x: x.state not in (SKIP, DONE))
        return bool(tasks)

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
            rec.invoice_journal_id = (invoice_journals[:1]).id

    def _get_file_id_for_log(self):
        return self.order_id._get_file_id_for_log()

    def manual_run(self):
        self.ensure_one()
        job_kwargs = self.order_id._job_kwargs_run_integration_workflow()

        context = {
            'company_id': self.order_id.company_id.id,
            'job_integration_id': self.order_id.integration_id.id,
            'job_integration_job_type': 'order',
            'job_order_id': self.order_id.id,
        }
        self \
            .with_context(**context) \
            .with_delay(**job_kwargs) \
            .trigger_pipeline()

        return self.open_form()

    def clear_info(self):
        self.current_info = False
        return self.open_form()

    def drop_pipeline(self):
        return self.unlink()

    def mark_input_as_done(self):
        self._mark_input_as_done()
        return self.open_form()

    def _mark_input_as_done(self):
        self.input_file_id.action_done()

    def _mark_input_to_process(self):
        self.input_file_id.action_process()

    def trigger_pipeline(self):
        _logger.info('Running integration pipeline → %s', str(self.loginfo))
        if not self.has_tasks_to_process:
            _logger.info('Skipping integration pipeline → %s', str(self.loginfo))
            self._mark_input_as_done()
            return _('Workflow Ended: %s') % self._tasks_info()

        task_to_run = self.pipeline_task_ids.filtered(lambda x: x.is_not_done)[:1]
        task_to_run.run_with_delay()

        self._mark_input_to_process()
        return self._tasks_info()

    def _call_pipeline_step(self, step_name):
        if not self.has_tasks_to_process:
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
            'name': _('Integration Workflow'),
            'res_model': self._name,
            'view_mode': 'form',
            'view_id': self.env.ref('integration.integration_workflow_pipeline_form_view').id,
            'res_id': self.id,
            'target': 'new',
        }
