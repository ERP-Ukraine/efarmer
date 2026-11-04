# See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api

from ...tools import is_translated_value


class IntegrationResLangMapping(models.Model):
    _name = 'integration.res.lang.mapping'
    _inherit = 'integration.mapping.mixin'
    _description = 'Integration Res Lang Mapping'
    _mapping_fields = ('language_id', 'external_language_id')
    _mapping_label = 'Language'

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
    def to_external_record(self, integration, odoo_value, raise_error=True):
        """Resolve an Odoo language to the external language to export it as.

        Args:
            integration (recordset): the store the mapping belongs to.
            odoo_value (recordset): `res.lang` to resolve.
            raise_error (bool): raise when the language was never mapped.

        Returns:
            recordset: single `integration.res.lang.external`.

        Several external languages may point at one Odoo language — two Magento store views
        with `en_US` and `en_GB` locales both map to Odoo `en_US` when `en_GB` is not
        installed. The mixin picks `id desc`, i.e. whichever mapping happened to be created
        last, so the store could receive `en_GB` content for `en_US`. Prefer the external
        whose code equals the Odoo language code, then the oldest mapping, which is stable
        across re-imports. This applies to every connector, not only Magento.
        """
        internal_field_name, external_field_name = self._mapping_fields

        mappings = self.search([
            ('integration_id', '=', integration.id),
            (internal_field_name, '=', odoo_value.id),
        ], order='id asc')

        if not mappings:
            return super().to_external_record(integration, odoo_value, raise_error=raise_error)

        preferred = mappings.filtered(
            lambda m: m[external_field_name].code == odoo_value.code
        )[:1]
        mapping = preferred or mappings[:1]

        return mapping[external_field_name]

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
