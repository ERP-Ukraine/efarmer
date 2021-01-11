from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    send_forecasted_report_recipients = fields.Boolean('Forecasted Report Recipient', default=False)
