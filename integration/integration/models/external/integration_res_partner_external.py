# See LICENSE file for full copyright and licensing details.

from odoo import models


class IntegrationResPartnerExternal(models.Model):
    _name = 'integration.res.partner.external'
    _inherit = 'integration.external.mixin'
    _description = 'Integration Res Partner External'
    _odoo_model = 'res.partner'
