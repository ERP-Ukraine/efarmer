from odoo import fields, models


class AccountAccountTag(models.Model):
    _inherit = 'account.account.tag'

    jpk_account_tag_ids = fields.One2many('jpk.account.tag', 'account_tag_id', 'JPK Account Tag')
