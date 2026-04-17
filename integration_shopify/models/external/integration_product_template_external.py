# See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.addons.integration.tools import MergeableDict


class IntegrationProductTemplateExternal(models.Model):
    _inherit = 'integration.product.template.external'

    def import_translations(self, force_import: bool = False):
        self.ensure_one()
        if not self.integration_id.is_integration_shopify:
            raise NotImplementedError

        # 1. Prepare translations data
        data = self.with_context(
            integration_first_time_import=force_import,
        ).prepare_translations_data_in()

        # 2. Apply transalations
        template = self.odoo_record.with_context(skip_product_export=True)
        self.create_or_update_with_translations(self.integration_id.id, template, data, translations_only=True)

        return data

    def prepare_translations_data_in(self):
        self.ensure_one()
        if not self.integration_id.is_integration_shopify:
            raise NotImplementedError

        integration = self.integration_id
        force_import = bool(self.env.context.get('integration_first_time_import'))  # Boolean, not the None type

        if not integration.is_translations_needed(force_import=force_import):
            return {}

        # 0. Fetch translations
        translations_data = self.fetch_translations()

        # 1. Format translations `like Presta`
        translations = {}
        for field, value in translations_data.items():
            translations[field] = {
                'language': [
                    {'attrs': {'id': k}, 'value': v} for k, v in value.items()
                ],
            }

        # 2. Convert external language codes to odoo language codes
        for key, value in translations.items():
            translations[key] = self.env['integration.res.lang.mapping'] \
                .convert_external_translations(integration.id, value)

        # 3. Convert technical fields to odoo fields
        add_domain = [('is_translatable_field', '=', True)]
        if force_import:
            add_domain.append(('import_enabled', '=', True))

        data = dict()
        template = self.odoo_record.with_context(skip_product_export=True)
        for mapping in template._get_ecommerce_fields_mappings(integration.id, add_domain):
            key = mapping.get_translation_key(field_name_only=False)

            if key in translations:
                odoo_name = mapping.ecommerce_field_id.get_odoo_field_name(raise_if_not_found=True)
                data[odoo_name] = translations[key]

        return data

    def fetch_translations(self):
        self.ensure_one()
        if not self.integration_id.is_integration_shopify:
            raise NotImplementedError

        # 1. Fetch translations
        resources = self._fetch_translations()

        if any(x.has_nested_metafields for x in resources):
            adapter = self.integration_id.adapter
            product = adapter.gql.Product.set(id=self.code)

            # 2. Parse translations
            product.get_metafields()
            metafields = {x.gid: x.to_dict() for x in product.metafields}
        else:
            metafields = {}

        mergeable_dict = MergeableDict()

        for resource in resources:
            resource.add_metafield_data(metafields)
            data = resource.parse_translations()
            mergeable_dict.merge(**data)

        return mergeable_dict.dump()

    def _fetch_translations(self):
        adapter = self.integration_id.adapter
        product = adapter.gql.Product.set(id=self.code)

        translate_resource = adapter.gql.TranslatableResource

        lang_codes = self.env['integration.res.lang.mapping'].search([
            ('language_id', '!=', False),
            ('integration_id', '=', self.integration_id.id),
        ]).mapped(lambda x: x.external_language_id.code)

        for code in lang_codes:
            translate_resource.add_target_to_pull(product.gid, code)

        return translate_resource.pull()

    def push_translations(self, force_export: bool = False):
        self.ensure_one()
        if not self.integration_id.is_integration_shopify:
            raise NotImplementedError

        # 1. Prepare translations data
        data = self.with_context(
            integration_force_product_export=force_export,
        ).prepare_translations_data_out()

        if not data:
            return []

        # 2. Push translations
        translation = self.integration_id.adapter.gql.Translation.set(**data)
        result = translation.push()

        return [x.to_dict() for x in result]

    def prepare_translations_data_out(self):
        self.ensure_one()
        if not self.integration_id.is_integration_shopify:
            raise NotImplementedError

        integration = self.integration_id
        force_export = bool(self.env.context.get('integration_force_product_export'))  # Boolean, not the None type

        if not integration.is_translations_needed(force_export=force_export):
            return {}

        # 1. Calculate export fields data
        add_domain = [('is_translatable_field', '=', True)]
        if not force_export:
            add_domain.append(('export_enabled', '=', True))

        template = self.odoo_record
        template.ensure_one()

        values = template \
            .with_context(
                integration_serialize_translations=True,
                integration_force_product_export=force_export,
            ) \
            .calculate_export_fields_data(integration.id, add_domain)

        adapter = integration.adapter

        # 2. Fetch product metafields
        if any(x.startswith('metafields.') for x in values.keys()):
            product = adapter.gql.Product.set(id=self.code)
            product.get_metafields()
            metafields = {x.gid: x.to_dict() for x in product.metafields}
        else:
            metafields = {}

        # 3. Fetch actual translatable content
        product = adapter.gql.Product.set(id=self.code)

        translate_resource = adapter.gql.TranslatableResource
        translate_resource.fetch_translatable_content(product.gid)

        translate_resource.add_metafield_data(metafields)

        # 4. Preare translations payload
        primary_lang = adapter.lang
        translation = adapter.gql.Translation

        for key, value in values.items():
            if key.startswith('metafields.'):
                metafield = translate_resource.get_metafield_by_key(key)
                if not metafield:
                    continue

                gid = metafield.gid
                key_ = 'value'

                primary_value = metafield['value']
            else:
                gid = product.gid
                key_ = key

                primary_value = translate_resource.get_primary_value_by_key(key_)

            for lang, value_ in value['language'].items():
                if (lang == primary_lang) or (not primary_value):
                    continue

                translation.add_target_to_push(gid, key_, value_, primary_value, lang)

        return translation.to_dict()
