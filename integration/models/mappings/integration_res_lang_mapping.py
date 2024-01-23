# See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class IntegrationResLangMapping(models.Model):
    _name = 'integration.res.lang.mapping'
    _inherit = 'integration.mapping.mixin'
    _description = 'Integration Res Lang Mapping'
    _mapping_fields = ('language_id', 'external_language_id')

    language_id = fields.Many2one(
        comodel_name='res.lang',
        ondelete='set null',
    )

    external_language_id = fields.Many2one(
        comodel_name='integration.res.lang.external',
        required=True,
        ondelete='cascade',
    )

    _sql_constraints = [
        (
            'uniq_mapping',
            'unique(integration_id, external_language_id)',
            'Language mapping should be unique per integration'
        ),
    ]
