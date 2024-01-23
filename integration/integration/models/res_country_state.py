# See LICENSE file for full copyright and licensing details.

from odoo import models


class ResCountryState(models.Model):
    _name = 'res.country.state'
    _inherit = ['res.country.state', 'integration.model.mixin']
    _internal_reference_field = 'code'
