# See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class IntegrationResCountryMapping(models.Model):
    _name = 'integration.res.country.mapping'
    _inherit = 'integration.mapping.mixin'
    _description = 'Integration Res Country Mapping'
    _mapping_fields = ('country_id', 'external_country_id')
    _mapping_label = 'Country'

    country_id = fields.Many2one(
        string='Odoo Country',
        comodel_name='res.country',
        ondelete='set null',
    )

    external_country_id = fields.Many2one(
        string='External Country',
        comodel_name='integration.res.country.external',
        required=True,
        ondelete='cascade',
    )

    _uniq_mapping = models.Constraint(
        'unique(integration_id, external_country_id)',
        'State mapping should be unique per integration',
    )
