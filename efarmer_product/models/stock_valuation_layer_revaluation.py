# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import _, api, models
from odoo.exceptions import UserError


class StockValuationLayerRevaluation(models.TransientModel):
    _inherit = 'stock.valuation.layer.revaluation'

    # This is OVERRIDE method for
    # remove UserError(_("You cannot revalue a product with an empty or negative stock."))
    # Task EF-270
    @api.model
    def default_get(self, default_fields):
        res = super().default_get(default_fields)
        if res.get('product_id'):
            product = self.env['product.product'].browse(res['product_id'])
            if product.categ_id.property_cost_method == 'standard':
                raise UserError(_("You cannot revalue a product with a standard cost method."))
            if 'account_journal_id' not in res and 'account_journal_id' in default_fields and product.categ_id.property_valuation == 'real_time':
                accounts = product.product_tmpl_id.get_product_accounts()
                res['account_journal_id'] = accounts['stock_journal'].id
        return res
