from odoo import _, api, models
from odoo.exceptions import ValidationError


class AccountAccount(models.Model):
    _inherit = 'account.account'

    @api.constrains('tag_ids')
    def _x_check_s_12_tags(self):
        for account_id in self:
            for prefix in {'S_12_1', 'S_12_2'}:
                if len(account_id.tag_ids.filtered(lambda t_id: t_id.name.startswith(f'{prefix}__'))) > 1:
                    raise ValidationError(_('Account %s can have only one %s tag.', account_id, prefix))
