# -*- coding: utf-8 -*-
from odoo import models


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    def action_create_payments(self):
        res = super(AccountPaymentRegister, self).action_create_payments()
        for payment in self:
            account_moves = self.env["account.move"].search(
                [
                    ("name", "in", payment.mapped("communication")),
                    ("invoice_origin", "!=", False),
                    ("payment_state", "!=", "not_paid"),
                ]
            )
            sale_orders = self.env["sale.order"].search(
                [
                    ("name", "in", account_moves.mapped("invoice_origin")),
                    ("paid_on_date", "=", False),
                ]
            )
            for move in account_moves:
                sale_order = sale_orders.filtered(
                    lambda order: order.name == move.invoice_origin
                )
                if sale_order:
                    sale_order.write({"paid_on_date": payment.payment_date})

        return res
