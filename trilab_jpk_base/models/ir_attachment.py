from pathlib import Path

from odoo import api, fields, models, tools


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    x_full_path = fields.Char(compute='x_compute_full_path')
    x_size = fields.Integer(compute='x_compute_full_path')

    @api.depends('store_fname')
    def x_compute_full_path(self):
        filestore = Path(tools.config.filestore(self.env.cr.dbname))

        for record in self:
            full_path = filestore / record.store_fname
            record.x_full_path = full_path.absolute()
            record.x_size = full_path.stat().st_size
