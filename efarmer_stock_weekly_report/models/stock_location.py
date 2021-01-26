import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

from ..utils import StockWeeklyReportProvider

_logger = logging.getLogger(__name__)

class StockLocation(models.Model):
    _inherit = 'stock.location'

    used_for_efarmer_stock_weekly_report = fields.Boolean('Stock Weekly Report', default=False)

    @api.constrains('used_for_efarmer_stock_weekly_report')
    def _check_used_for_efarmer_stock_weekly_report(self):
        records = self.sudo().search([('used_for_efarmer_stock_weekly_report', '=', True)])
        if len(records) > 1:
            raise UserError('You\'ve already set a location for Stock Weekly Report.')

    @api.model
    def build_weekly_report(self):
        return StockWeeklyReportProvider(self.env).get_report()

    @api.model
    def cron_efarmer_stock_weekly_report(self):
        recipient_ids = self.env['res.partner'].sudo().search([('stock_weekly_report_recipient', '=', True)]).ids
        if not recipient_ids:
            _logger.warning('No recipient found! Set ones on the contact form or disable the scheduled action.')
            return

        email_from = self.env['ir.mail_server'].search([('smtp_user', '!=', False)], limit=1).smtp_user
        if not email_from:
            _logger.warning('There is no outgoing server with username / email. The report won\'t be sent!')
            return

        try:
            data = self.build_weekly_report()
        except Exception as e:
            _logger.warning(e)
            return

        mail = self.env['mail.mail'].create({
            'email_from': email_from,
            'subject': 'Weekly Report',
            'body_html': '',
            'recipient_ids': recipient_ids,
        })

        attachment_ids = [(0, 0, {
            'name': 'Weekly Report.xlsx',
            'datas': data,
            'type': 'binary',
            'res_model': 'mail.message',
            'res_id': mail.mail_message_id.id,
        })]

        mail.write({'attachment_ids': attachment_ids})
        mail.send()
