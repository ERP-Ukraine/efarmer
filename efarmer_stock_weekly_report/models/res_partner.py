from odoo import fields, models

class ResPartner(models.Model):
    _inherit = 'res.partner'

    stock_weekly_report_recipient = fields.Boolean('Weekly Report Recipient', default=False)
