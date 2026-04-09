# See LICENSE file for full copyright and licensing details.

from functools import reduce
from itertools import groupby
from operator import attrgetter
from collections import defaultdict

from odoo import api, models, fields


class ExternalStockLocationLine(models.Model):
    _name = 'external.stock.location.line'
    _description = 'External Stock Location Line'
    _rec_name = 'location_name'

    location_name = fields.Char(
        string='Location Name',
        compute='_compute_location_name',
    )

    integration_id = fields.Many2one(
        string='E-Commerce Store',
        comodel_name='sale.integration',
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
    warehouse_id = fields.Many2one(
        comodel_name='stock.warehouse',
        related='erp_location_id.warehouse_id',
    )

    @api.depends('erp_location_id', 'external_location_id')
    def _compute_location_name(self):
        for record in self:
            name_parts = []

            if record.external_location_id:
                name_parts.append(record.external_location_id.display_name)

            if record.erp_location_id:
                name_parts.append(f'({record.erp_location_id.display_name})')

            if name_parts:
                record.location_name = ' '.join(name_parts)
            else:
                record.location_name = f'Record ID: {record.id}'

    def _group_by_external_code(self):
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
