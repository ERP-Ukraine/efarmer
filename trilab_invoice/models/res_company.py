from odoo import fields, models


class Company(models.Model):
    _inherit = 'res.company'

    x_use_ti = fields.Boolean(string='Use Trilab Invoice Module')
    x_show_price_before_discount = fields.Boolean(string='Show Price Before Discount on Invoices')
    x_hide_zero_price_aml = fields.Boolean(string='Hide Zero Price AML on Invoices')
    x_sale_down_payment_product_id = fields.Many2one(
        comodel_name='product.product',
        string='Downpayment Product',
        domain=[
            ('type', '=', 'service'),
            ('invoice_policy', '=', 'order'),
        ],
        help='Default product used for down payments',
        check_company=True,
    )
    x_no_reverse_moves_reconcile = fields.Boolean(string='Disable Reversed Moves Automatic Reconciliation')
    x_company_partner_bank_on_proforma = fields.Boolean('Show Company Partner Bank on Pro-Forma')
