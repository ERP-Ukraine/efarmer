from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'


    youtrack_id = fields.Char()
