# See LICENSE file for full copyright and licensing details.

from odoo import models
import logging

_logger = logging.getLogger(__name__)


class IntegrationResCountryExternal(models.Model):
    _name = 'integration.res.country.external'
    _inherit = 'integration.external.mixin'
    _description = 'Integration Res Country External'
    _odoo_model = 'res.country'
