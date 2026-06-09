# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models
from odoo.exceptions import UserError


class SaleOrderCancel(models.TransientModel):
    _inherit = 'sale.order.cancel'

    integration_id = fields.Many2one(
        string='E-Commerce Store',
        comodel_name='sale.integration',
        related='order_id.integration_id'
    )

    @property
    def integration_input_file(self):
        return self.order_id.related_input_files[:1]

    def _check_integration_order_status(self):
        return self

    def _action_cancel_integration(self):
        return True, ''

    def action_cancel_integration(self):
        __, errors = self._action_cancel_integration()

        if errors:
            raise UserError(errors)

        return {
            'type': 'ir.actions.act_window_close',
        }

    def action_cancel(self):
        res = super().action_cancel()

        if self.integration_id.is_active and self.integration_id.is_integration_cancel_allowed():
            self_ = self._check_integration_order_status()
            return self_.open_integration_cancel_view()

        return res

    def action_send_mail_and_cancel(self):
        res = super().action_send_mail_and_cancel()

        if self.integration_id.is_active and self.integration_id.is_integration_cancel_allowed():
            self_ = self._check_integration_order_status()
            return self_.open_integration_cancel_view()

        return res

    def open_integration_cancel_view(self):
        file_name = self.integration_input_file.name if self.integration_input_file else 'No External Record'
        return {
            'type': 'ir.actions.act_window',
            'name': (
                f'{self.integration_id.name}: '
                f'Cancel Order {self.order_id.external_sales_order_ref} ({file_name})',
            ),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.integration_id._get_cancel_order_view_id(),
            'target': 'new',
            'context': self.env.context,
        }
