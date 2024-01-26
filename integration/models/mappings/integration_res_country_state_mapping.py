# See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class IntegrationResCountryStateMapping(models.Model):
    _name = 'integration.res.country.state.mapping'
    _inherit = 'integration.mapping.mixin'
    _description = 'Integration Res Country State Mapping'
    _mapping_fields = ('state_id', 'external_state_id')

    state_id = fields.Many2one(
        comodel_name='res.country.state',
        ondelete='set null',
    )

    external_state_id = fields.Many2one(
        comodel_name='integration.res.country.state.external',
        required=True,
        ondelete='cascade',
    )

    _sql_constraints = [
        (
            'uniq_mapping',
            'unique(integration_id, external_state_id)',
            'Country State mapping should be unique per integration'
        ),
    ]
