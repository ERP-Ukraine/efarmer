# See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class IntegrationResCountryMapping(models.Model):
    _name = 'integration.res.country.mapping'
    _inherit = 'integration.mapping.mixin'
    _description = 'Integration Res Country Mapping'
    _mapping_fields = ('country_id', 'external_country_id')

    country_id = fields.Many2one(
        comodel_name='res.country',
        ondelete='set null',
    )

    external_country_id = fields.Many2one(
        comodel_name='integration.res.country.external',
        required=True,
        ondelete='cascade',
    )

    _sql_constraints = [
        (
            'uniq_mapping',
            'unique(integration_id, external_country_id)',
            'State mapping should be unique per integration'
        ),
    ]
