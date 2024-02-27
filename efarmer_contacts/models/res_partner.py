# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from odoo import api, models


_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def vies_vat_check(self, country_code, vat_number):
        '''
        Function overwrites the original one in order to skip VIES check for polish companies
        '''
        if country_code.upper() == self.env.ref('base.pl').code.upper():
            _logger.info(f'VIES check was skipped for polish company {self.name} with VAT {vat_number}')
            return True
        else:
            return super().vies_vat_check(country_code, vat_number)
