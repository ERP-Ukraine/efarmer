# See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.addons.queue_job.job import Job
from odoo.tools.misc import clean_context


class Base(models.AbstractModel):
    _inherit = 'base'

    def job_log(self, job, delay=False):
        if not isinstance(job, Job):
            return self.env['job.log']

        record = job.db_record()
        if not record:
            return False

        ctx = self.env.context
        int_ctx_id = ctx.get('default_integration_id', False)

        integration = record.integration_id
        integration = integration or integration.browse(int_ctx_id)
        if not integration and integration._name == self._name:
            integration = integration.browse(self.ids)
        integration.exists().ensure_one()

        if delay:
            job_kwargs = {
                'priority': 25,
                'description': f'{integration.name}: Create Job Logs with delay ({self._name})',
            }
            job = self.with_delay(**job_kwargs)._job_log(record, integration.id)
            return job

        return self._job_log(record, integration.id)

    def _job_log(self, queue_job, integration_id):
        vals = dict(
            job_id=queue_job.id,
            res_model=self._name,
            integration_id=integration_id,
        )
        ctx = clean_context(self.env.context)

        def prepare_vals(rec):
            return {'res_id': rec.id, **vals}

        return self.env['job.log'].sudo().with_context(ctx).create([prepare_vals(x) for x in self])

    def get_formview_action_log(self):
        return self.get_formview_action()

    def _get_field_string(self, name):
        if name in self._fields:
            return self._fields[name].string
        return name
