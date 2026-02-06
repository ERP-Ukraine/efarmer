from odoo import fields, models


class AccountPaymentTerm(models.Model):
    _inherit = 'account.payment.term'

    x_ksef_payment_term_type = fields.Selection(
        selection=[
            ('1', 'Cash'),
            ('2', 'Card'),
            ('3', 'Voucher'),
            ('4', 'Cheque'),
            ('5', 'Credit'),
            ('6', 'Bank Transfer'),
            ('7', 'Mobile Payment'),
        ],
        string='KSeF Payment Term Type',
    )
    x_ksef_payment_state_mapping = fields.Selection(
        selection=[
            ('paid', 'Paid'),
            ('not_paid', 'Not Paid'),
        ],
        string='KSeF Payment Status Mapping',
    )
