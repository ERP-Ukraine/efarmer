# Copyright 2025 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

import re
from odoo.addons.trilab_jpk_vat.reports.jpk_vat7m_v2 import JpkReportV2


def extract_kwota_expression(sql: str) -> str:
    sql = re.sub(r'\s+', ' ', sql.strip())

    pattern = r'(SUM\(CASE.*?END\))\s+AS\s+kwota'
    match = re.search(pattern, sql, re.IGNORECASE)

    if match:
        return match.group(1).strip()
    return "0"


original_get_query = JpkReportV2._get_query


def patched_get_query():
    query = original_get_query()
    kwota_expr = extract_kwota_expression(query)
    query = query.replace(
        "ORDER BY",
        f"HAVING {kwota_expr} * SIGN(AVG(jat.jpk_apply_to::int)) >= 0\nORDER BY"
    )
    return query

JpkReportV2._get_query = staticmethod(patched_get_query)
