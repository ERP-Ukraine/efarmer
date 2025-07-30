from odoo import fields, models


class StockProductionLot(models.Model):
    _inherit = 'stock.production.lot'
    
    is_unused = fields.Boolean(
        string='Unused',
        compute='_compute_is_unused',
        search='_search_is_unused',
        store=False
    )
    
    def _compute_is_unused(self):
        move_line_model = self.env['stock.move.line']
        for lot in self:
            # Check if this lot has ever been used in any move line
            used = move_line_model.search_count([
                ('lot_id', '=', lot.id),
                ('state', '=', 'done')
            ], limit=1)
            lot.is_unused = not used
    
    def _search_is_unused(self, operator, value):
        if operator not in ('=', '!=') or not isinstance(value, bool):
            return []
            
        # Find all lots that appear in done move lines
        self.env.cr.execute("""
            SELECT DISTINCT lot_id 
            FROM stock_move_line 
            WHERE lot_id IS NOT NULL 
            AND state = 'done'
        """)
        used_lot_ids = [r[0] for r in self.env.cr.fetchall()]
        
        if value:
            # Return lots NOT in the used list
            return [('id', 'not in', used_lot_ids)]
        else:
            # Return lots in the used list
            return [('id', 'in', used_lot_ids)]
