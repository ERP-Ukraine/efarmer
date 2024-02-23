# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api
from odoo.tools.safe_eval import safe_eval


class SaleIntegrationAPIFields(models.Model):
    _name = 'sale.integration.api.field'
    _description = 'Sale Integration API Fields'

    name = fields.Char(
        string='Name',
        required=True,
    )
    description = fields.Char(
        string='Description',
    )
    value = fields.Char(
        string='Value',
    )
    sia_id = fields.Many2one(
        'sale.integration',
        string='API Service',
        ondelete='cascade',
    )
    eval = fields.Boolean(
        string='Eval',
    )
    is_secure = fields.Boolean(
        string='Is Secure',
    )

    def get_eval_globals(self):
        self.ensure_one()
        eval_globals = {
            'record': self.sia_id,
        }
        return eval_globals

    @api.model
    def to_dictionary(self):
        sia_fields = {}
        for field in self:
            value = field.value

            if field.eval and value:
                eval_globals = field.get_eval_globals()
                value = safe_eval(field.value, eval_globals)

            sia_fields[field.name] = {
                'name': field.name,
                'description': field.description,
                'value': value,
                'eval': field.eval,
                'is_secure': field.is_secure,
            }

        return sia_fields
