# See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api

from ...tools import is_translated_value


class IntegrationResLangMapping(models.Model):
    _name = 'integration.res.lang.mapping'
    _inherit = 'integration.mapping.mixin'
    _description = 'Integration Res Lang Mapping'
    _mapping_fields = ('language_id', 'external_language_id')

    language_id = fields.Many2one(
        string='Odoo Language',
        comodel_name='res.lang',
        ondelete='set null',
    )

    external_language_id = fields.Many2one(
        string='E-Commerce Store Language',
        comodel_name='integration.res.lang.external',
        required=True,
        ondelete='cascade',
    )

    _uniq_mapping = models.Constraint(
        'unique(integration_id, external_language_id)',
        'Language mapping should be unique per integration',
    )

    @api.model
    def convert_external_translations(self, integration_id: int, value: str):
        if not is_translated_value(value):
            return value

        language_mappings = self.search([
            ('integration_id', '=', integration_id),
        ])

        language_codes = {x.external_language_id.code: x.language_id.id for x in language_mappings}

        if isinstance(value['language'], dict):
            value['language'] = [value['language']]

        result = {}

        for translation in value['language']:
            external_language_id = translation['attrs']['id']

            if external_language_id in language_codes:
                result[language_codes[external_language_id]] = translation['value']

        return {'language': result}

    @api.model
    def has_more_than_one_mapping(self, integration_id: int):
        return self.search_count([
            ('language_id', '!=', False),
            ('integration_id', '=', integration_id),
        ]) > 1
