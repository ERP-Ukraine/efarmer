from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    x_enable_invoice_rate_change = fields.Boolean('Enable Invoice Rate Change')


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    x_enable_invoice_rate_change = fields.Boolean(related='company_id.x_enable_invoice_rate_change', readonly=False)
