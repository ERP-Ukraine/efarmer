# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


SALE_CARDS_TYPE = 'get-sales-cards'
SALE_DATA_TYPE = 'get-sales-data'
TOP_PRODUCTS_TYPE = 'get-top-products'
STORE_PERFORMANCE_TYPE = 'get-store-performance'


class IntegrationDashboardCache(models.TransientModel):
    _name = 'integration.dashboard.cache'
    _description = 'Integration Dashboard Cache'
    _order = 'id desc'
    _transient_max_hours = 24

    tag = fields.Char(
        string='Tag',
        required=True,
    )

    timestamp = fields.Char(
        string='Epoch Timestamp ',
        required=True,
    )

    ttype = fields.Selection(
        selection=[
            (SALE_CARDS_TYPE, 'Sales Cards'),
            (SALE_DATA_TYPE, 'Sales Data'),
            (TOP_PRODUCTS_TYPE, 'Top Products'),
            (STORE_PERFORMANCE_TYPE, 'Store Performance'),
        ],
        string='Type',
        required=True,
    )

    data = fields.Json(
        string='Data',
    )

    @api.model
    def get_last_record(self, ttype: str, tag: str) -> dict:
        self.env.cr.execute(
            f"""
            SELECT id, timestamp, data from {self._table}
            WHERE ttype = '{ttype}' AND tag = '{tag}'
            ORDER BY id DESC
            LIMIT 1
            """
        )
        return self.env.cr.dictfetchone() or dict()
