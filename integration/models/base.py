# See LICENSE file for full copyright and licensing details.

import logging

from odoo import models
from odoo.addons.queue_job.job import Job
from odoo.tools.misc import clean_context


_logger = logging.getLogger(__name__)


class Base(models.AbstractModel):
    _inherit = 'base'

    def job_log(self, job):
        if not isinstance(job, Job):
            return self.env['job.log']

        record = job.db_record()
        if not record:
            return False

        integration = record.integration_id
        int_ctx_id = self.env.context.get('default_integration_id', False)
        integration = integration or integration.browse(int_ctx_id)

        if not integration and integration._name == self._name:
            integration = integration.browse(self.ids)

        integration.exists().ensure_one()

        if not record.integration_id:
            record.integration_id = integration.id

        return self._job_log(record, integration.id)

    def _job_log(self, queue_job, integration_id):
        vals = dict(
            job_id=queue_job.id,
            res_model=self._name,
            integration_id=integration_id,
        )

        job_log = self.env['job.log'].sudo() \
            .with_context(clean_context(self.env.context)) \
            .create([{'res_id': x.id, **vals} for x in self])

        _logger.info('JobLog was created: %s', str(job_log.loginfo))
        return job_log

    def get_formview_action_log(self):
        return self.get_formview_action()

    def is_module_installed(self, name):
        module = self.sudo().env.ref(f'base.module_{name}', raise_if_not_found=False)
        return (module.state == 'installed') if module else False

    def _get_field_string(self, name):
        if name in self._fields:
            return self._fields[name].string
        return name
