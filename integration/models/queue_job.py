# See LICENSE file for full copyright and licensing details.

import re

from odoo import api, models, fields, _
from odoo.exceptions import UserError
from odoo.addons.integration_queue_job.job import Job


MODELS_WITH_IMPORT_AVAILABLE = [
    'product.attribute.value',
    'res.country',
    'account.tax',
    'res.lang',
    'sale.order.payment.method',
    'product.product',
    'ecommerce.product.category',
    'product.template',
    'delivery.carrier',
    'res.country.state',
    'account.tax.group',
    'sale.order.sub.status',
    'product.attribute',
]
JOB_STATE_FAILED = 'failed'

# Mapping from job context keys to corresponding field names
JOB_CONTEXT_TO_FIELD_MAPPING = {
    'job_integration_id': 'integration_id',
    'job_integration_job_type': 'integration_job_type',
    'job_external_template_id': 'external_template_id',
    'job_template_id': 'template_id',
    'job_input_file_id': 'input_file_id',
    'job_order_id': 'order_id',
    'job_related_record_model': 'related_record_model',
    'job_related_record_ids': 'related_record_ids',
}


class QueueJob(models.Model):
    _inherit = 'queue.job'
    _removal_interval = 15

    # Custom fields for integration jobs
    integration_id = fields.Many2one(
        comodel_name='sale.integration',
        string='E-Commerce Store',
    )

    integration_job_type = fields.Selection(
        selection=[
            ('initial_import', 'Initial Import'),
            ('product', 'Product Sync'),
            ('customer', 'Customer Sync'),
            ('order', 'Orders Sync'),
            ('inventory', 'Inventory Sync'),
            ('pricelist', 'Pricelist Sync'),
            ('other', 'Other'),
        ],
        string='Job Type',
        default='other',
    )

    parent_id = fields.Many2one(
        comodel_name='queue.job',
        string='Parent Job',
        ondelete='cascade',
    )

    # Links to different types of records to make it easier to track jobs
    external_template_id = fields.Many2one(
        comodel_name='integration.product.template.external',
        string='External Product',
        ondelete='cascade',
    )

    template_id = fields.Many2one(
        comodel_name='product.template',
        string='Product',
        ondelete='cascade',
    )

    input_file_id = fields.Many2one(
        comodel_name='sale.integration.input.file',
        string='Order Data',
        ondelete='cascade',
    )

    order_id = fields.Many2one(
        comodel_name='sale.order',
        related='input_file_id.order_id',
        string='Order',
        store=True,
    )

    # Mass actions on multiple records. We store model and IDs of related records for better performance
    related_record_model = fields.Char(
        string='Entity',
    )

    related_record_ids = fields.Json(
        string='Entity IDs',
    )

    # TODO: Review fields below - are they needed?
    integration_exception_name = fields.Selection(
        selection=[
            (
                'NotMappedFromExternal',
                'E-Commerce System object not mapped with Odoo. Try to import external records '
                'from E-Commerce System, map it by hands or import into Odoo.'
            ),
            (
                'NotMappedToExternal',
                'Odoo object not mapped with E-Commerce System. Try to import external records '
                'from E-Commerce System and map it.'
            ),
            (
                'NoExternal',
                'External record doesn\'t exist. Try to import external records '
                'from E-Commerce System.'
            ),
        ],
        string='Exception Name',
    )

    integration_model_name = fields.Text(
        string='Integration Model Name',
    )

    integration_key = fields.Text(
        string='External or Internal Key',
    )

    integration_model_view_name = fields.Text(
        string='Model Name',
        compute='_compute_view_name',
    )

    integration_external_id = fields.Text(
        string='External ID',
        compute='_compute_ids',
    )

    integration_odoo_id = fields.Integer(
        string='Odoo ID',
        compute='_compute_ids',
    )

    integration_external_name = fields.Text(
        string='External Name',
        compute='_compute_names',
    )

    integration_odoo_name = fields.Text(
        string='Odoo Name',
        compute='_compute_names',
    )

    exc_info_lite = fields.Char(
        string='Exception Info Lite',
        compute='_compute_exc_info_lite',
    )

    toggle_exc = fields.Boolean(
        string='Full Traceback',
    )

    is_import_from_external_available = fields.Boolean(
        string='Import from External Available',
        compute='_compute_is_import_from_external_available',
        help=(
            'Indicates whether the "Import External Records From E-Commerce System" button '
            'should be visible.'
        ),
    )

    @api.depends('integration_id', 'integration_model_name')
    def _compute_is_import_from_external_available(self):
        for record in self:
            model = record.get_model_from_integration_model_name()
            record.is_import_from_external_available = self.integration_id \
                and model in MODELS_WITH_IMPORT_AVAILABLE

    def _compute_exc_info_lite(self):
        for rec in self:
            rec.exc_info_lite = rec._sub_compute_exc_info_lite()

    def _sub_compute_exc_info_lite(self):
        info = self.exc_info or str()
        if not info:
            return info
        info_split = info.rsplit('File', maxsplit=1)[-1]
        exc = info_split.split('\n', maxsplit=1)[-1]
        return exc

    @api.model_create_multi
    def create(self, vals_list):
        if not vals_list:
            # Fix for badly written parent method - it will raise an error
            return self.browse()

        # Fill integration fields from context (if any)
        # Map context payload into job fields (only if not already set)
        for vals in vals_list:
            for ctx_key, field in JOB_CONTEXT_TO_FIELD_MAPPING.items():
                if self.env.context.get(ctx_key) and not vals.get(field):
                    vals[field] = self.env.context[ctx_key]

        records = super(QueueJob, self).create(vals_list)

        return records

    def write(self, vals):
        result = super(QueueJob, self).write(vals)

        if not vals.get('state') == 'failed':
            return result

        exception_names = 'NotMappedFromExternal|NotMappedToExternal|NoExternal'
        for job in self:
            # This construction need to clean variables if error fixed
            integration_exception_name = None
            integration_model_name = None
            integration_key = None
            integration_id = job.integration_id.id

            if job.exc_info:
                match = re.search(
                    r'(%s): (.*)\((code|id)=(.*), integration=(.*)\)' % exception_names,
                    job.exc_info,
                )
                if match:
                    integration_exception_name = match.group(1)
                    integration_model_name = match.group(2)
                    integration_key = match.group(4)
                    integration_id = match.group(5)

            # This fields used for re-run jobs on fixed mapping
            if integration_id:
                job.write({
                    'integration_exception_name': integration_exception_name,
                    'integration_model_name': integration_model_name,
                    'integration_key': integration_key,
                    'integration_id': int(integration_id),
                })

        return result

    @api.model
    def requeue_integration_jobs(self, exception_name, model_name, key):
        jobs = self.sudo().search([
            ('state', '=', JOB_STATE_FAILED),
            ('integration_exception_name', '=', exception_name),
            ('integration_model_name', '=', model_name),
            ('integration_key', '=', key),
        ])

        if jobs:
            jobs.requeue()

    def get_model_from_integration_model_name(self):
        if not self.integration_model_name:
            return ''

        match = re.search(r'integration.(.*)(.mapping|.external)', self.integration_model_name)

        if match:
            return match.group(1)
        else:
            return ''

    def _compute_view_name(self):
        for job in self:
            model = job.get_model_from_integration_model_name()

            try:
                job.integration_model_view_name = self.env[model]._description
            except KeyError:
                job.integration_model_view_name = None

    def _compute_ids(self):
        for job in self:
            external_id = None
            odoo_id = None

            if job.integration_key:
                if job.integration_exception_name == 'NotMappedToExternal':
                    odoo_id = int(job.integration_key)
                else:
                    external_id = job.integration_key

            job.integration_external_id = external_id
            job.integration_odoo_id = odoo_id

    def _compute_names(self):
        for job in self:
            external_name = None
            odoo_name = None

            model = job.get_model_from_integration_model_name()

            if model and job.integration_exception_name:
                try:
                    if job.integration_exception_name == 'NotMappedToExternal':
                        odoo_name = self.env[model].search(
                            [('id', '=', job.integration_odoo_id)]
                        ).name
                    elif job.integration_id:
                        external_model = 'integration.%s.external' % model
                        external_name = self.env[external_model].search([
                            ('code', '=', job.integration_external_id),
                            ('integration_id', '=', job.integration_id.id),
                        ]).name
                except KeyError:
                    pass

            job.integration_external_name = external_name
            job.integration_odoo_name = odoo_name

    def _subscribe_users_domain(self):
        domain = super()._subscribe_users_domain()
        domain.append(('notify_failed_jobs', '=', True))
        return domain

    def action_open_related_records(self):
        self.ensure_one()

        if not self.related_record_model or not self.related_record_ids:
            return

        try:
            model = self.env[self.related_record_model]
        except KeyError:
            raise UserError(_(
                'The model "%s" does not exist in the system anymore. '
                'Please contact support: https://support.ventor.tech/'
            ) % self.related_record_model)

        records = model.browse(self.related_record_ids)

        if not records:
            return

        return {
            'name': _('Related Records'),
            'type': 'ir.actions.act_window',
            'view_mode': 'list,form',
            'res_model': self.related_record_model,
            'domain': [('id', 'in', records.ids)],
            'target': 'current',
        }

    def action_open_mapping_view(self):
        model = self.get_model_from_integration_model_name()

        if model:
            action_name = 'integration.integration_%s_mapping_action' % model.replace('.', '_')

            return self.env.ref(action_name).read()[0]

    def action_open_external_view(self):
        model = self.get_model_from_integration_model_name()

        if model:
            action_name = 'integration.integration_%s_external_action' % model.replace('.', '_')

            return self.env.ref(action_name).read()[0]

    def action_import_from_external_system(self):
        """
        The `Import External Records From E-Commerce System` button.
        """
        model = self.get_model_from_integration_model_name()
        external_model_name = 'integration.%s.external' % model
        external_model = self.env[external_model_name]

        # Fetch the old records before the import
        external_old = external_model.search([
            ('integration_id', '=', self.integration_id.id)
        ])

        # Map models to their corresponding import methods
        import_methods = {
            'product.attribute.value': self.integration_id.integrationApiImportAttributeValues,
            'res.country': self.integration_id.integrationApiImportCountries,
            'account.tax': self.integration_id.integrationApiImportTaxes,
            'res.lang': self.integration_id.integrationApiImportLanguages,
            'sale.order.payment.method': self.integration_id.integrationApiImportPaymentMethods,
            'product.product': self.integration_id.integrationApiImportProducts,
            'ecommerce.product.category': self.integration_id.integrationApiImportCategories,
            'product.template': self.integration_id.integrationApiImportProducts,
            'delivery.carrier': self.integration_id.integrationApiImportDeliveryMethods,
            'res.country.state': self.integration_id.integrationApiImportStates,
            'sale.order.sub.status': self.integration_id.integrationApiImportSaleOrderStatuses,
            'product.attribute': self.integration_id.integrationApiImportAttributes,
        }

        # Run the corresponding import method based on the model
        import_method = import_methods.get(model)
        if import_method:
            import_method()
        else:
            raise UserError(_(
                'The model "%s" is not supported for direct import.\n\n'
                'It is possible that this model can only be imported as part of the "Import Master Data" process.\n\n'
                'Please try running "Import Master Data" from the "Initial Import" tab in '
                'the "%s" integration settings. '
                'If you encounter this error, please contact our support team: https://support.ventor.tech/'
            ) % (model, self.integration_id.name))

        # Fetch new records after the import
        external_new = external_model.search([
            ('integration_id', '=', self.integration_id.id)
        ])

        external_delta = external_new - external_old
        message = _('"%s" import has been completed.') % external_model._description

        # If old records were updated, show a message with the count
        if external_old:
            message += _('\nUpdated records: %s') % len(external_old)

        # If new records were imported, show a detailed message with record codes and names
        if external_delta:
            if message:
                message += '\n\n'

            message += _('\nImported new external records: %s') % len(external_delta)
            for external in external_delta:
                message += '\n\t%s\t%s' % (str(external.code), external.name)

        # Display the message in a wizard form
        message_id = self.env['message.wizard'].create({'message': message})

        return {
            'name': _('Import list of %s') % self.integration_model_view_name,
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'message.wizard',
            'res_id': message_id.id,
            'target': 'new'
        }

    def action_run_now(self):
        """Run the job synchronously in real time (debug tool)."""
        self.ensure_one()
        job = Job.load(self.env, self.uuid)
        job.set_started()
        job.store()
        try:
            result = job.perform()
            job.set_done(result=result)
            job.enqueue_waiting()
            job.store()
        except Exception as e:
            raise UserError(_('Job failed:\n\n%s') % str(e))

    def action_toggle_exc(self):
        self.toggle_exc = not self.toggle_exc
        return self.action_open_lite_info()

    def action_open_lite_info(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Job Info',
            'res_model': self._name,
            'view_mode': 'form',
            'view_id': self.env.ref('integration.view_queue_job_lite_info_form').id,
            'res_id': self.id,
            'target': 'new',
        }
