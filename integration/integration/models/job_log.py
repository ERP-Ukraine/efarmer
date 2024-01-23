# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api


class JobLog(models.Model):
    _name = 'job.log'
    _description = 'Job Log'
    _order = 'id desc'

    name = fields.Char(
        compute='_compute_name',
        string='Related Object',
    )
    job_id = fields.Many2one(
        comodel_name='queue.job',
        string='Job',
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
    template_id = fields.Many2one(
        comodel_name='product.template',
        string='Product',
        ondelete='cascade',
    )
    integration_id = fields.Many2one(
        comodel_name='sale.integration',
        string='Integration',
    )
    state = fields.Selection(
        related='job_id.state',
    )
    date_created = fields.Datetime(
        related='job_id.date_created',
    )
    res_model = fields.Char(
        string='Related Model',
    )
    res_id = fields.Integer(
        string='Related ID',
    )
    exc_info_lite = fields.Char(
        string='Exception Info',
        compute='_compute_exc_info_lite',
        compute_sudo=True,
        store=True,
    )

    @property
    def odoo_id(self):
        self.ensure_one()
        rec = self.env[self.res_model].browse(self.res_id)
        return rec.exists()

    def _compute_name(self):
        for rec in self:
            odoo_id = rec.odoo_id
            rec.name = odoo_id and odoo_id.display_name

    @api.depends('job_id.state')
    def _compute_exc_info_lite(self):
        for rec in self:
            rec.exc_info_lite = rec.job_id._sub_compute_exc_info_lite()

    @api.model_create_multi
    def create(self, vals_list):
        result = super(JobLog, self).create(vals_list)
        for rec in result:
            rec._assign_related()
        return result

    def _assign_related(self):
        record = self.odoo_id
        vals = {
            'template_id': getattr(record, '_get_tmpl_id_for_log', lambda: False)(),
            'input_file_id': getattr(record, '_get_file_id_for_log', lambda: False)(),
        }
        return self.write(vals)

    def action_requeue_job(self):
        return self.job_id.requeue()

    def action_set_job_done(self):
        return self.job_id.button_done()

    def action_open_odoo(self):
        record = self.order_id or self.input_file_id or self.template_id or self.odoo_id
        return record.get_formview_action_log()

    def action_open_job_lite_info(self):
        self.job_id.toggle_exc = False
        return self.job_id.action_open_lite_info()

    def open_tree_view(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Job Logs',
            'res_model': self._name,
            'view_mode': 'tree',
            'view_id': self.env.ref('integration.integration_job_log_view_tree').id,
            'domain': [('id', 'in', self.ids)],
            'target': 'current',
        }
