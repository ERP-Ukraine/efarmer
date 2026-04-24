from io import BytesIO
from typing import Any, Iterable, Optional

import xlsxwriter
from odoo import models
from xlsxwriter.worksheet import Worksheet


class CellDefinition:
    def __init__(
        self,
        field: Optional[str],
        name: str,
        data_type: str = 'text',
        style: Optional[str] = None,
        width: Optional[int] = None,
    ):
        self.field = field
        self.name = name
        self.data_type = data_type
        self.style = style
        self.width = width


class XlsxHelper(models.AbstractModel):
    _name = 'jpk.trilab.export_helper'
    _description = 'Trilab Export Helper'

    _xlsx_styles = {}

    xlsx_styles = {
        'default': {'font_size': 12},
        'monetary': {'font_size': 12, 'num_format': '##0.00'},
        'title': {'bold': True, 'bottom': 2},
    }

    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    def get_workbook_options(self, options):
        return {}

    def _get_report_data(self, doc_ids, options):
        raise NotImplementedError()

    def generate_xlsx_report(self, workbook: xlsxwriter.Workbook, doc_ids: Optional[Iterable[int]], options: dict):
        raise NotImplementedError()

    def generate_xml_report(self, file_data: BytesIO, doc_ids: Optional[Iterable[int]], options: dict):
        raise NotImplementedError()

    def generate_xlsx_styles(self, workbook: xlsxwriter.Workbook):
        for style_name, style_props in self.xlsx_styles.items():
            self._xlsx_styles[style_name] = workbook.add_format(style_props)
            self._xlsx_styles[f'{style_name}_date'] = workbook.add_format({**style_props, 'num_format': 'yyyy-mm-dd'})

    def create_xlsx_report(self, doc_ids, options):
        file_data = BytesIO()
        workbook = xlsxwriter.Workbook(file_data, self.get_workbook_options(options))
        self.generate_xlsx_styles(workbook)
        self.generate_xlsx_report(workbook, doc_ids, options)
        workbook.close()
        return file_data.getvalue(), 'xlsx'

    def _write_cell(
        self,
        worksheet: Worksheet,
        ypos: int,
        xpos: int,
        value: Any,
        definition: Optional[CellDefinition] = None,
        style: Optional[str] = None,
        colspan: int = 1,
    ):
        if not style and definition and definition.style:
            style = definition.style

        if not style:
            style = 'default'

        if style and definition and definition.data_type == 'date':
            style = f'{style}_date'

        if definition and definition.data_type == 'text' and not isinstance(value, str):
            if not value:
                value = None

        if colspan == 1:
            worksheet.write(ypos, xpos, value, self._xlsx_styles.get(style))

        else:
            worksheet.merge_range(ypos, xpos, ypos, ypos + colspan - 1, value, self._xlsx_styles.get(style))

    def create_xml_report(self, doc_ids, options):
        file_data = BytesIO()
        self.generate_xml_report(file_data, doc_ids, options)
        return file_data.getvalue(), 'xml'
