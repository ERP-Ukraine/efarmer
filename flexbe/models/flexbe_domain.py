import urllib
from odoo import api, fields, models


class FlexbeDomain(models.Model):
    _name = 'flexbe.domain'
    _description = 'Flexbe Domain'

    name = fields.Char('Domain')

    @api.model
    def is_valid_domain(self, domain):
        return bool(self.sudo().search([('name', '=', domain)]))
