from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    x_ksef_third_party_ids = fields.One2many('ksef.third_party', 'sale_order_id', string='KSeF Third Parties')

    def _prepare_invoice(self):
        invoice_vals = super()._prepare_invoice()

        invoice_vals['x_ksef_third_party_ids'] = [fields.Command.set(self.x_ksef_third_party_ids.ids)]

        return invoice_vals
