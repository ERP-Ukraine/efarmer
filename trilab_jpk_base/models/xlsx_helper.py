import base64
import datetime
import tempfile

import xlsxwriter

from odoo import models


class Cell:
    def __init__(self, value, style=None, default_value='-'):
        self._value = value
        self.style = style
        self.default_value = default_value

    @property
    def value(self):
        if self._value is None:
            return
        return self._value or self.default_value


class XlsxHelper(models.AbstractModel):
    _name = 'trilab.xlsx_helper'
    _description = 'Trilab Xlsx Helper'

    def create_xlsx_report(self, data: dict, file_name, res_id=None, res_model=None):
        """
        :param data: dictionary with worksheet name and its data {
            'worksheet1': [
                ['A', 'B', 'C'],
                [1, 2, 3],
                [4, 5, 6],
            ],
        }
        :param file_name: xlsx file name
        :param res_id: attachment res_id
        :param res_model: attachment res_model
        """
        file_path = tempfile.mktemp(suffix='.xlsx')
        workbook = xlsxwriter.Workbook(file_path)

        bold_center = workbook.add_format(
            {'bold': True, 'align': 'center', 'valign': 'vcenter', 'bg_color': '#E0E0E0', 'border': 1}
        )
        date_format = workbook.add_format({'num_format': 'yyyy-mm-dd'})
        default_value = self._context.get('x_default_value')

        for worksheet_name, worksheet_data in data.items():
            worksheet = workbook.add_worksheet(worksheet_name)

            # Iterate over worksheet_data by columns and set max column width
            for x, column in enumerate(zip(*worksheet_data)):
                max_width = 0
                for y, value in enumerate(column):
                    cell = Cell(value)
                    if default_value:
                        cell.default_value = default_value
                    if y == 0:
                        cell.style = bold_center
                    elif isinstance(cell.value, datetime.date):
                        cell.style = date_format
                    worksheet.write(y, x, cell.value, cell.style)
                    cell_len = len(str(cell.value))
                    if cell_len > max_width:
                        max_width = cell_len
                worksheet.set_column(x, x, max_width + 10)

        workbook.close()

        with open(file_path, 'rb') as r:
            xlsx_file = base64.b64encode(r.read())

        attachment_vals = {'name': file_name, 'type': 'binary', 'datas': xlsx_file}

        if res_id and res_model:
            attachment_vals.update({'res_id': res_id, 'res_model': res_model})

        return self.env['ir.attachment'].create(attachment_vals)
