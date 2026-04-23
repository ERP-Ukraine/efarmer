from odoo import models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def x_action_invoice_report_xlsx(self):
        return {
            'type': 'ir.actions.report',
            'report_name': 'trilab_jpk_vat.invoice_report',
            'docids': self.ids,
            'data': {},
            'report_type': 'jpk_xlsx',
            'name': 'Invoices XSLX',
        }
