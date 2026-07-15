# Copyright 2025 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

import re

from odoo import models
from odoo.addons.trilab_jpk_base.models.export_helper import CellDefinition
from odoo.addons.trilab_jpk_vat.reports.jpk_vat7m import JpkVat7MReport
from odoo.addons.trilab_jpk_vat.reports.jpk_vat7m_v3 import JpkReportV3


def extract_kwota_expression(sql: str) -> str:
    sql = re.sub(r'\s+', ' ', sql.strip())

    pattern = r'(SUM\(CASE.*?END\))\s+AS\s+kwota'
    match = re.search(pattern, sql, re.IGNORECASE)

    if match:
        return match.group(1).strip()
    return '0'


class JpkReportV3Extension(models.AbstractModel):
    _inherit = 'report.trilab_jpk_vat.jpk_vat7m_v3_report'

    grouping_columns = JpkReportV3.grouping_columns + [CellDefinition('nrksef', 'Nr KSeF')]
    columns = grouping_columns + JpkVat7MReport.detail_columns

    @staticmethod
    def _get_query():
        query = JpkReportV3._get_query()

        kwota_expr = extract_kwota_expression(query)
        return query.replace(
            'ORDER BY',
            f'HAVING {kwota_expr} * SIGN(AVG(jat.jpk_apply_to::int)) >= 0\nORDER BY',
        )
