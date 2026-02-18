# See LICENSE file for full copyright and licensing details.

from odoo import models, tools


class ResCurrency(models.Model):
    _inherit = 'res.currency'

    def round(self, amount):
        self.ensure_one()
        precision_rounding = self.env.context.get('precision_rounding')

        if precision_rounding:
            return tools.float_round(amount, precision_rounding=precision_rounding)

        return super(ResCurrency, self).round(amount)
