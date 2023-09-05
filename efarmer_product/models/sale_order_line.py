# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import fields, models, api


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # OVERRIDE METHOD
    def _compute_tax_id(self):
        for line in self:
            line = line.with_company(line.company_id)
            fpos = line.order_id.fiscal_position_id or line.order_id.fiscal_position_id.get_fiscal_position(line.order_partner_id.id)
            # This filter need for search goods products in SO and set all taxes like a goods product
            # Task EF-182-change-doc-layout
            goods_product_lines = line.order_id.order_line.filtered(
                lambda x: x.product_id.product_func_id.name == 'Goods'
            )
            if goods_product_lines:
                # If company_id is set, always filter taxes by the company
                taxes = goods_product_lines[0].product_id.taxes_id.filtered(lambda t: t.company_id == line.env.company)
                line.order_id.order_line.tax_id = fpos.map_tax(taxes, goods_product_lines)
            else:
                # If company_id is set, always filter taxes by the company
                taxes = line.product_id.taxes_id.filtered(lambda t: t.company_id == line.env.company)
                line.tax_id = fpos.map_tax(taxes, line)
