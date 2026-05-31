# See LICENSE file for full copyright and licensing details.

from odoo import models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.sql import escape_psql


class IntegrationProductElementValueMappingMixin(models.AbstractModel):
    """Shared behavior for product attribute / feature value mapping models.

    Concrete models must set ``_value_element`` to either ``'attribute'`` or
    ``'feature'``. The mixin uses it to address the matching parent mapping
    model (``integration.product.<element>.mapping``) and Odoo value model
    (``product.<element>.value``).
    """
    _name = 'integration.product.element.value.mapping.mixin'
    _description = 'Integration Product Element Value Mapping Mixin'
    _value_element = None

    def run_auto_link(self):
        return self._auto_link_value_mappings()

    def _auto_link_value_mappings(self):
        """Link selected value mappings to existing Odoo records by name.

        Each record's parent attribute/feature must already be mapped — values
        are searched within the parent's scope, in the integration's configured
        language. Already-mapped, no-match and ambiguous rows are reported in a
        summary wizard rather than aborting the batch.
        """
        element = self._value_element
        if element not in ('attribute', 'feature'):
            raise ValidationError(_(
                'Auto-Link supports only "attribute" or "feature" value mappings. '
                'This is a technical issue — please contact support: https://support.ventor.tech/'
            ))

        if not self:
            return self.env['message.wizard'].create_and_run(
                _('No records selected.')
            )

        ElementMapping = self.env[f'integration.product.{element}.mapping']
        ElementValue = self.env[f'product.{element}.value']

        value_internal_field, value_external_field = self._mapping_fields
        parent_external_field = f'external_{element}_id'
        parent_internal_field = f'{element}_id'

        # 1. Validate every integration has a language configured. This raises
        #    a friendly UserError for any integration with integration_lang_id
        #    unset, before we touch any data.
        for integration in self.mapped('integration_id'):
            integration.get_integration_lang_code()

        # 2. Resolve and cache parent attribute/feature mappings, collect any
        #    that are not mapped to an Odoo record so we can fail loudly with
        #    a single user-friendly error rather than silently skipping rows.
        parent_cache = {}
        unmapped_parents = []
        for record in self:
            ext_value = record[value_external_field]
            ext_parent = ext_value[parent_external_field]
            key = (record.integration_id.id, ext_parent.id)
            if key in parent_cache:
                continue

            parent_mapping = ElementMapping.search([
                ('integration_id', '=', record.integration_id.id),
                (parent_external_field, '=', ext_parent.id),
            ], limit=1)
            odoo_parent = parent_mapping[parent_internal_field] \
                if parent_mapping else ElementMapping.browse()

            parent_cache[key] = odoo_parent
            if not odoo_parent:
                unmapped_parents.append((record.integration_id, ext_parent))

        if unmapped_parents:
            details = '\n'.join(
                '- [%s] %s (code=%s)' % (integ.name, ext_parent.name, ext_parent.code)
                for integ, ext_parent in unmapped_parents
            )
            raise UserError(_(
                'Cannot Auto-Link the selected value mappings — the following '
                '%(elements)s are not mapped yet:\n%(details)s\n\n'
                'Open the %(element_cap)s Mappings view, map (or run "Import %(element_cap)s") '
                'on these records first, then re-run Auto-Link on the value mappings.'
            ) % {
                'elements': element + 's',
                'element_cap': element.capitalize(),
                'details': details,
            })

        # 3. Try to link each unmapped value by name within parent scope.
        counters = {'linked': 0, 'already_linked': 0, 'no_match': 0, 'ambiguous': 0}
        no_match = []
        ambiguous = []

        for record in self:
            if record[value_internal_field]:
                counters['already_linked'] += 1
                continue

            ext_value = record[value_external_field]
            ext_parent = ext_value[parent_external_field]
            odoo_parent = parent_cache[(record.integration_id.id, ext_parent.id)]

            lang_code = record.integration_id.get_integration_lang_code()
            candidates = ElementValue.with_context(lang=lang_code).search([
                (parent_internal_field, '=', odoo_parent.id),
                ('name', '=ilike', escape_psql(ext_value.name)),
            ])

            if len(candidates) == 1:
                record[value_internal_field] = candidates.id
                counters['linked'] += 1
            elif not candidates:
                counters['no_match'] += 1
                no_match.append(ext_value.display_name)
            else:
                counters['ambiguous'] += 1
                ambiguous.append((ext_value.display_name, candidates.mapped('name')))

        # 4. Build a human-readable summary for the wizard.
        lines = [
            _('Auto-Link results:'),
            '',
            _('Linked: %s') % counters['linked'],
            _('Already linked: %s') % counters['already_linked'],
            _('No match: %s') % counters['no_match'],
            _('Ambiguous (multiple Odoo candidates): %s') % counters['ambiguous'],
        ]
        if no_match:
            lines.append('')
            lines.append(_('No Odoo match found for:'))
            lines.extend('- %s' % name for name in no_match)
        if ambiguous:
            lines.append('')
            lines.append(_('Multiple Odoo candidates (left unmapped — please link manually):'))
            for name, options in ambiguous:
                lines.append(_('- "%(ext)s" matches: %(options)s') % {
                    'ext': name,
                    'options': ', '.join(options),
                })

        return self.env['message.wizard'].create_and_run('\n'.join(lines))
