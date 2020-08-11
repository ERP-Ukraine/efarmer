from odoo import models


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    def action_new_quotation(self):
        self.ensure_one()
        action = super().action_new_quotation()

        assert isinstance(action, dict)
        assert isinstance(action.get('context'), dict)
        action['context'].update({
            'default_utm_term_id': self.utm_term_id.id,
            'default_utm_content_id': self.utm_content_id.id,
        })

        return action
