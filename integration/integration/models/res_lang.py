# See LICENSE file for full copyright and licensing details.

from odoo import models


class ResLang(models.Model):
    _name = 'res.lang'
    _inherit = ['res.lang', 'integration.model.mixin']
    _internal_reference_field = 'code'
