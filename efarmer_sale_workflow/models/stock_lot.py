from odoo import api, fields, models


class StockLot(models.Model):
    _inherit = "stock.lot"

    is_unused = fields.Boolean(
        string="Unused",
        compute="_compute_is_unused",
        search="_search_is_unused",
        store=False,
    )

    def _check_unused_lots(self):
        lot_ids = self.ids
        where = "lot_id IS NOT NULL" if not lot_ids else "lot_id IN %s"
        params = () if not lot_ids else (tuple(lot_ids),)
        self.env.cr.execute(
            f"""
            SELECT DISTINCT lot_id
            FROM stock_move_line
            WHERE {where} AND state = 'done'
        """,
            params,
        )
        return [r[0] for r in self.env.cr.fetchall()]

    def _compute_is_unused(self):
        used_lot_ids = self._check_unused_lots()
        for lot in self:
            lot.is_unused = lot.id not in used_lot_ids

    @api.model
    def _search_is_unused(self, operator, value):
        if operator not in ("=", "!=") or not isinstance(value, bool):
            return []
        used_lot_ids = self._check_unused_lots()
        if value:
            # Return lots NOT in the used list
            return [("id", "not in", used_lot_ids)]
        else:
            # Return lots in the used list
            return [("id", "in", used_lot_ids)]
