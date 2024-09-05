from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    x_jpk_lock_date = fields.Date(string='JPK Lock Date', help='Lock date for JPK reporting')
