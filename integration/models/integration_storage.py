# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class IntegrationStorage(models.TransientModel):
    """Generic, abstract key/value scratch storage for multi-step processing.

    Used to temporarily persist partial results produced by a sequence of
    background jobs so that a later step can read and combine them. Rows are
    grouped by an arbitrary ``key`` (e.g. a run token); each row carries a JSON
    ``value``. Not tied to any particular feature.

    Records are garbage-collected automatically by the transient vacuum
    (``_transient_max_hours``); callers should also explicitly drop their rows
    via :meth:`pop_values` once a run is finished.
    """
    _name = 'integration.storage'
    _description = 'Integration Storage'
    _order = 'id'
    _transient_max_hours = 24

    key = fields.Char(
        string='Key',
        required=True,
        index=True,
    )

    value = fields.Json(
        string='Value',
    )

    @api.model
    def push(self, key, value):
        """Persist a single ``value`` under ``key`` and return the new record."""
        return self.create({'key': key, 'value': value})

    @api.model
    def read_values(self, key):
        """Return the list of ``value`` payloads stored under ``key``."""
        records = self.search([('key', '=', key)])
        return [record.value for record in records]

    @api.model
    def pop_values(self, key):
        """Return all ``value`` payloads stored under ``key`` and drop the rows."""
        records = self.search([('key', '=', key)])
        values = [record.value for record in records]
        records.unlink()
        return values
