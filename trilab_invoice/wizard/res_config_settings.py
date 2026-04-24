from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    x_use_trilab_invoice = fields.Boolean(related='company_id.x_use_ti', readonly=False)
    x_show_price_before_discount = fields.Boolean(related='company_id.x_show_price_before_discount', readonly=False)
    x_hide_zero_price_aml = fields.Boolean(related='company_id.x_hide_zero_price_aml', readonly=False)
    x_sale_down_payment_product_id = fields.Many2one(
        related='company_id.x_sale_down_payment_product_id', readonly=False
    )
    x_no_reverse_moves_reconcile = fields.Boolean(related='company_id.x_no_reverse_moves_reconcile', readonly=False)
    x_company_partner_bank_on_proforma = fields.Boolean(
        related='company_id.x_company_partner_bank_on_proforma', readonly=False
    )
