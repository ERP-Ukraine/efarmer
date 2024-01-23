# See LICENSE file for full copyright and licensing details.

from odoo import models
import logging

_logger = logging.getLogger(__name__)


class IntegrationSaleOrderExternal(models.Model):
    _name = 'integration.sale.order.external'
    _inherit = 'integration.external.mixin'
    _description = 'Integration Sale Order External'
    _odoo_model = 'sale.order'
