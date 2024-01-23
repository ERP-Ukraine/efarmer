# See LICENSE file for full copyright and licensing details.

import logging

from odoo import models, fields, _
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
    integration_id = fields.Many2one(
        comodel_name='sale.integration',
        related='pipeline_id.order_id.integration_id',
    )
    pipeline_id = fields.Many2one(
        comodel_name='integration.workflow.pipeline',
        string='Pipeline',
        ondelete='cascade',
    )
    skip_dispatch = fields.Boolean(
        related='pipeline_id.skip_dispatch',
    )

    def _compute_name(self):
        for rec in self:
            rec.name = ' '.join([x.capitalize() for x in rec.current_step_method.split('_')])

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
        self.mark_done()
        self.update_info()
        if update_logs:
            self.mark_jobs_as_done()
        return True

    def run(self):
        """Manual running by button"""
        if self.state in (SKIP, DONE):
            raise UserError(_('Inactive task for the current workflow!'))

        self._validate_previous()
        order_method = self._retrieve_current_order_method()
        result, message = order_method()

        if result:
            self.set_task_to_done()
            if not self.get_next_task():
                self.mark_input_as_done()
        else:
            self.mark_process()
            self.update_info(message)

        return self.open_form()

    def run_with_delay(self):
        """Automatic running by triggered `pipeline_id`"""
        job_kwargs = self._build_task_job_kwargs()
        job = self.with_delay(**job_kwargs)._run_and_call_next()
        self.order_id.job_log(job)
        return job

    def mark_jobs_as_done(self):
        job_log_ids = self.env['job.log'].search([
            ('state', '=', 'done'),
            ('res_id', '=', self.id),
            ('res_model', '=', self._name),
            ('integration_id', '=', self.integration_id.id),
        ])
        return job_log_ids.mapped('job_id').button_done()

    def get_formview_action_log(self):
        return self.pipeline_id.get_formview_action_log()

    def _fail_job_manually(self, message):
        job_kwargs = self._build_task_job_kwargs()
        job = self.with_delay(**job_kwargs)._raise_message(message)
        self.order_id.job_log(job)
        return job

    def _build_task_job_kwargs(self):
        return {
            'channel': self.env.ref('integration.channel_sale_order').complete_name,
            'identity_key': f'integartion_pipeline_task-{self.integration_id.id}-{self}',
            'description': 'Workflow Line: '
            + f'{self.name} [{self.order_id.display_name}] ({self.integration_id.id})',
        }

    def _raise_message(self, message):
        info = _(
            'This is just an information message. Mark this job as done (no need to requeue) '
            'and fix all the issues related to %s order by clicking on the '
            '"Integration Workflow" button on the order\'s form.'
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
        states = self.pipeline_id.pipeline_task_ids\
            .filtered(lambda x: x.id < self.id and x.state != SKIP).mapped('state')

        if states and not all(x == DONE for x in states):
            raise UserError(
                _('Not the all previous tasks in the state DONE. Fix them first.')
            )

    def _get_integration_id_for_job(self):
        return self.integration_id.id

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
        string='Input File Update Required',
    )
    sub_state_external_ids = fields.Many2many(
        comodel_name='integration.sale.order.sub.status.external',
        relation='pipeline_external_sub_state_relation',
        column1='pipeline_id',
        column2='sub_state_external_id',
        string='External Sub Status Code',
    )
    invoice_journal_id = fields.Many2one(
        comodel_name='account.journal',
        compute='_compute_invoice_journal',
        string='Invoice Journal',
    )
    force_invoice_date = fields.Boolean(
        string='Force Invoice Date',
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

    def _compute_invoice_journal(self):
        for rec in self:
            invoice_journals = rec.sub_state_external_ids\
                .mapped('invoice_journal_id')
            rec.invoice_journal_id = (invoice_journals[:1]).id

    def _get_integration_id_for_job(self):
        return self.order_id.integration_id.id

    def _get_file_id_for_log(self):
        return self.order_id._get_file_id_for_log()

    def manual_run(self):
        self.ensure_one()
        job_kwargs = self.order_id._build_workflow_job_kwargs()
        job = self.with_delay(**job_kwargs).trigger_pipeline()
        self.order_id.job_log(job)
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

    def trigger_pipeline(self):
        self.input_file_id.action_process()
        task_to_run = self.pipeline_task_ids.filtered(lambda x: x.is_not_done)[:1]

        if not task_to_run:
            self._mark_input_as_done()
            return _(
                'There are no active tasks for the current pipeline: %s' % self._tasks_info()
            )
        task_to_run.run_with_delay()
        return self._tasks_info()

    def _call_pipeline_step(self, step_name):
        task_to_run = self._find_task(step_name)
        if not task_to_run:
            self._mark_input_as_done()
            return _('Workflow Done!')

        return task_to_run.run_with_delay()

    def _find_task(self, step_name):
        task_to_run = self.pipeline_task_ids\
            .filtered(lambda x: x.current_step_method == step_name)
        return task_to_run

    def _tasks_info(self):
        return [(x.name, x.state) for x in self.pipeline_task_ids]

    def _update_pipeline(self, order_data):
        _logger.info('Update existing order pipeline %s', self)

        task_list, pipeline_vals = self.order_id._build_task_list_and_vals(order_data)
        sub_state_ids = pipeline_vals['sub_state_external_ids'][0][-1]
        payment_method_external_id = pipeline_vals['payment_method_external_id']
        vals = {
            'sub_state_external_ids': [(4, x, 0) for x in sub_state_ids],
            'skip_dispatch': self._context.get('default_skip_dispatch', False),
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
                _logger.info('Pipeline task "%s" was marked as "TODO".', task_name)

        return vals

    def get_formview_action_log(self):
        return self.order_id.get_formview_action()

    def open_form(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Integration Workflow',
            'res_model': self._name,
            'view_mode': 'form',
            'view_id': self.env.ref('integration.integration_workflow_pipeline_form_view').id,
            'res_id': self.id,
            'target': 'new',
        }
