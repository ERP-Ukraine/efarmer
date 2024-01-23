# See LICENSE file for full copyright and licensing details.

from functools import reduce
from itertools import groupby
from operator import attrgetter
from collections import defaultdict

from odoo import models, fields


class ExternalStockLocationLine(models.Model):
    _name = 'external.stock.location.line'
    _description = 'External Stock Location Line'

    integration_id = fields.Many2one(
        comodel_name='sale.integration',
        string='Integration',
        ondelete='cascade',
        required=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        related='integration_id.company_id',
    )
    erp_location_id = fields.Many2one(
        comodel_name='stock.location',
        string='Location',
        ondelete='cascade',
        required=True,
    )
    external_location_id = fields.Many2one(
        comodel_name='integration.stock.location.external',
        string='External Location',
    )

    def _group_by_exernal_code(self):
        """
        Group self-recordset by `external_location_id`

        :return: [
            ('80295690532', stock.location(28,)),
            ('73153839396', stock.location(29, 32, 33)),
        ]
        """
        dict_ = defaultdict(list)
        [
            [dict_[key.code].append(x.erp_location_id) for x in grouper]
            for key, grouper in groupby(self, key=attrgetter('external_location_id'))
        ]
        return [(key, reduce(lambda a, b: a + b, val)) for key, val in dict_.items()]
