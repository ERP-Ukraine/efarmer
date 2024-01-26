# See LICENSE file for full copyright and licensing details.

import logging
from odoo import models

_logger = logging.getLogger(__name__)


class IntegrationSaleOrderLineExternal(models.Model):
    _name = 'integration.sale.order.line.external'
    _inherit = 'integration.external.mixin'
    _description = 'Integration Sale Order Line External'
    _odoo_model = 'sale.order.line'
