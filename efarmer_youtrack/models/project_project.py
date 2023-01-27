from odoo import api, fields, models, _, _lt

class Project(models.Model):
    _inherit = 'project.project'

    project_code = fields.Char(
        string='Project Code',
    )

    youtrack_id = fields.Char()
