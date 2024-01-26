# See LICENSE file for full copyright and licensing details.

from odoo import models
import logging

_logger = logging.getLogger(__name__)


class IntegrationResLangExternal(models.Model):
    _name = 'integration.res.lang.external'
    _inherit = 'integration.external.mixin'
    _description = 'Integration Res Lang External'
    _odoo_model = 'res.lang'
