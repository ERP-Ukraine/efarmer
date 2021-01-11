import io
import base64
import logging
from odoo import api, fields, models
from odoo.tools.misc import PatchedXlsxWorkbook

_logger = logging.getLogger(__name__)


class ReportStockQuantity(models.Model):
    _inherit = 'report.stock.quantity'

    @api.model
    def cron_send_forecasted_receipts_report(self):
        self.init()

        recipient_ids = self.env['res.partner'].sudo().search([('send_forecasted_report_recipients', '=', True)]).ids
        if not recipient_ids:
            _logger.warning('Forecasted Receipts Report: No recipient found! Set ones on the contact form or disable the scheduled action.')
            return

        email_from = self.env['ir.mail_server'].search([('smtp_user', '!=', False)], limit=1).smtp_user
        if not email_from:
            _logger.warning('Forecasted Receipts Report: There is no outgoing server with username / email. The report won\'t be sent!')
            return

        date_list = []
        product_list = []
        cells = {}

        domain = [('warehouse_id', '!=', False), ('state', '=', 'in'), ('date', '>=', fields.Date.today())]
        field_list = ['product_qty', 'date', 'product_id']
        group_by_fields = ['date:day', 'product_id']

        for item in self._read_group_raw(domain, field_list, group_by_fields, lazy=False, orderby='date ASC, product_id'):
            date = item['date:day'][1]
            if date not in date_list:
                date_list.append(date)

            product_id = item['product_id'][0]
            product_name = str(item['product_id'][1])
            product_list_item = (product_id, product_name)
            if product_list_item not in product_list:
                product_list.append(product_list_item)

            cells[(date, product_id)] = item['product_qty']

        stream = io.BytesIO()
        with PatchedXlsxWorkbook(stream) as workbook:
            format_col = workbook.add_format({'bold': True, 'border': True, 'align': 'center'})
            format_row = workbook.add_format({'bold': True, 'border': True, 'align': 'left'})
            format_cell = workbook.add_format({'num_format': '0.00', 'border': True, 'align': 'right'})

            worksheet = workbook.add_worksheet()

            # first line
            for col_no, date in enumerate(date_list, start=1):
                worksheet.write(0, col_no, date, format_col)

            # other lines
            for row_no, product_list_item in enumerate(product_list, start=1):
                worksheet.write(row_no, 0, product_list_item[1], format_row)
                for col_no, date in enumerate(date_list, start=1):
                    qty = cells.get((date, product_list_item[0]), 0.0)
                    worksheet.write(row_no, col_no, qty, format_cell)

            worksheet.set_column(0, 0, 40)  # the long first column for product names
            worksheet.set_column(1, len(date_list), 12)

        mail = self.env['mail.mail'].create({
            'email_from': email_from,
            'subject': 'Forecasted Receipts Report',
            'body_html': '',
            'recipient_ids': recipient_ids,
        })

        stream.seek(0)
        attachment_ids = [(0, 0, {
            'name': 'Forecasted Receipts Report.xlsx',
            'datas': base64.b64encode(stream.read()),
            'type': 'binary',
            'res_model': 'mail.message',
            'res_id': mail.mail_message_id.id,
        })]

        mail.write({'attachment_ids': attachment_ids})
        mail.send()
