# See LICENSE file for full copyright and licensing details.

from odoo import models


class IntegrationStockLocationExternal(models.Model):
    _name = 'integration.stock.location.external'
    _inherit = 'integration.external.mixin'
    _description = 'Integration Stock Location External'
    _odoo_model = 'stock.location'
