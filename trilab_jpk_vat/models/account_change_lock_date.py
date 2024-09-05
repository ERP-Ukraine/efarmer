from odoo import fields, models


class AccountChangeLockDate(models.TransientModel):
    _inherit = 'account.change.lock.date'

    x_jpk_lock_date = fields.Date(string='JPK Lock Date', default=lambda self: self.env.company.x_jpk_lock_date)

    def change_lock_date(self):
        result = super().change_lock_date()
        self.env.company.sudo().write({'x_jpk_lock_date': self.x_jpk_lock_date})
        return result
