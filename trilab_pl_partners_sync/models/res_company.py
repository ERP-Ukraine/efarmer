from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    x_pl_enable_gus = fields.Boolean()
    x_pl_enable_krd = fields.Boolean()

    x_pl_krd_env = fields.Selection([('prod', 'Production'), ('test', 'Testing')], default='test', string='KRD env')
    x_pl_krd_login = fields.Char('KRD Login')
    x_pl_krd_pass = fields.Char('KRD Password')

    x_pl_validate_vat = fields.Boolean(string='Validate VAT', help='Validate and block duplicate VAT')
