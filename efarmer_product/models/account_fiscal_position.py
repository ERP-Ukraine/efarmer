# Copyright 2026 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import api, fields, models


class AccountFiscalPosition(models.Model):
    _inherit = "account.fiscal.position"

    # OVERRIDE METHOD
    def map_tax(self, taxes, line=False):
        if not self:
            return taxes
        result = self.env["account.tax"]
        for tax in taxes:
            if line:
                taxes_correspondance = self.tax_ids.filtered(
                    lambda t: t.tax_src_id == tax._origin
                    and t.product_func_id
                    == line.product_id.product_tmpl_id.product_func_id
                    and t.country_id == line.order_id.partner_id.country_id
                    and t.partner_company_type == line.order_id.partner_id.company_type
                )
                if taxes_correspondance:
                    line.order_id.product_vat_id = taxes_correspondance.product_vat_id
            else:
                taxes_correspondance = self.tax_ids.filtered(
                    lambda t: t.tax_src_id == tax._origin
                )
            result |= taxes_correspondance.tax_dest_id if taxes_correspondance else tax
        return result
