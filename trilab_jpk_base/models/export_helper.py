from io import BytesIO
from typing import Any, Iterable

import xlsxwriter
from odoo import models
from odoo.tools.translate import LazyGettext
from xlsxwriter.worksheet import Worksheet


class CellDefinition:
    def __init__(
        self,
        field: str,
        name: str | LazyGettext,
        data_type: str = 'text',
        style: str | None = None,
        width: int | None = None,
    ):
        self.field = field
        self.name = name
        self.data_type = data_type
        self.style = style
        self.width = width


class StyledWorkbook(xlsxwriter.Workbook):
    def __init__(self, filename=None, options=None, styles: dict | None = None):
        super().__init__(filename, options)
        self._style_props = styles or {}
        self._style_formats = {}

    def add_worksheet(self, *args, **kwargs):
        worksheet = super().add_worksheet(*args, **kwargs)
        worksheet.styled_workbook = self
        return worksheet

    def get_style_format(self, style: str, is_date: bool = False):
        key = (style, is_date)

        if key not in self._style_formats:
            props = self._style_props.get(style)

            if props is not None and is_date:
                props = {**props, 'num_format': 'yyyy-mm-dd'}

            self._style_formats[key] = self.add_format(props) if props is not None else None

        return self._style_formats[key]


class XlsxHelper(models.AbstractModel):
    _name = 'jpk.trilab.export_helper'
    _description = 'Trilab Export Helper'

    xlsx_styles = {
        'default': {'font_size': 12},
        'monetary': {'font_size': 12, 'num_format': '##0.00'},
        'title': {'bold': True, 'bottom': 2},
    }

    # noinspection PyMethodMayBeStatic,unused-parameter
    def get_workbook_options(self, options):
        return {}

    def _get_report_data(self, doc_ids, options):
        raise NotImplementedError()

    def generate_xlsx_report(self, workbook: xlsxwriter.Workbook, doc_ids: Iterable[int] | None, options: dict):
        raise NotImplementedError()

    def generate_xml_report(self, file_data: BytesIO, doc_ids: Iterable[int] | None, options: dict):
        raise NotImplementedError()

    def create_xlsx_report(self, doc_ids, options):
        file_data = BytesIO()
        workbook = StyledWorkbook(file_data, self.get_workbook_options(options), styles=self.xlsx_styles)
        self.generate_xlsx_report(workbook, doc_ids, options)
        workbook.close()
        return file_data.getvalue(), 'xlsx'

    def _write_cell(
        self,
        worksheet: Worksheet,
        ypos: int,
        xpos: int,
        value: Any,
        definition: CellDefinition | None = None,
        style: str | None = None,
        colspan: int = 1,
    ):
        if not style and definition and definition.style:
            style = definition.style

        if not style:
            style = 'default'

        if definition and definition.data_type == 'text' and not isinstance(value, str):
            if not value:
                value = None

        cell_format = worksheet.styled_workbook.get_style_format(
            style, is_date=bool(definition and definition.data_type == 'date')
        )

        if colspan == 1:
            worksheet.write(ypos, xpos, value, cell_format)

        else:
            worksheet.merge_range(ypos, xpos, ypos, xpos + colspan - 1, value, cell_format)

    def create_xml_report(self, doc_ids, options):
        file_data = BytesIO()
        self.generate_xml_report(file_data, doc_ids, options)
        return file_data.getvalue(), 'xml'
