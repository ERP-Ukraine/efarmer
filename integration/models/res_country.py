# See LICENSE file for full copyright and licensing details.

from odoo import models


class ResCountry(models.Model):
    _name = 'res.country'
    _inherit = ['res.country', 'integration.model.mixin']
    _internal_reference_field = 'code'
