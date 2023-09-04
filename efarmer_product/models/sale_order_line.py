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
            # If company_id is set, always filter taxes by the company
            goods_product = line.order_id.order_line.filtered(lambda x: x.product_id.product_func_id.name == 'Goods')
            if goods_product:
                taxes = goods_product[0].taxes_id.filtered(lambda t: t.company_id == line.env.company)
                line.tax_id = fpos.map_tax(taxes, line)
            else:
                line.tax_id = fpos.map_tax(taxes, line)
