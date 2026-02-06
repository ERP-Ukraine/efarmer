from odoo import fields, models


class AccountAccountTag(models.Model):
    _inherit = 'account.account.tag'

    x_ksef_tax_tag_id = fields.Many2one('ksef.tax.tag', string='KSeF Tax Tag')
