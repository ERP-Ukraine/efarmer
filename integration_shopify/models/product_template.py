# See LICENSE file for full copyright and licensing details.

import logging

import requests

from odoo import models


_logger = logging.getLogger(__name__)

PRODUCT_IMAGE_CODE_PREFIX = 'ProductImage'


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    def to_export_format(self, integration):
        result = super().to_export_format(integration)

        if integration.is_integration_shopify:
            # Update external_id
            external_id = result['external_id']
            if external_id:
                adapter = integration.adapter
                value = adapter.gql.Product.create_gid(external_id)
            else:
                value = external_id

            result['gid'] = value

            # Update attribute_values to match Shopify format
            attribute_lines = self.attribute_line_ids \
                .filtered(lambda x: not x.exclude_from_synchronization)

            result['attribute_values'] = [x.to_export_format_gql(integration.id) for x in attribute_lines]

        return result

    def import_template_hook(self, integration_id: int, force_import: bool = False) -> None:
        integration = self.env['sale.integration'].browse(integration_id)

        if integration.is_integration_shopify and (
            integration.is_translations_needed(force_import=force_import)
        ):
            job_kwargs = self._job_kwargs_import_template_translations(integration_id)
            self \
                .with_context(company_id=integration.company_id.id) \
                .with_delay(**job_kwargs) \
                .integration_import_translations(integration_id, force_import)

    def export_template_hook(self, integration_id: int, force_export: bool = False) -> None:
        integration = self.env['sale.integration'].browse(integration_id)

        if integration.is_integration_shopify and (
            integration.is_translations_needed(force_export=force_export)
        ):
            job_kwargs = self._job_kwargs_export_template_translations(integration_id)
            self \
                .with_context(
                    job_integration_id=integration_id,
                    company_id=integration.company_id.id,
                ) \
                .with_delay(**job_kwargs) \
                .integration_export_translations(integration_id, force_export)

    def integration_import_translations(self, integration_id: int, force_import: bool) -> 'models.Model':
        integration = self.env['sale.integration'].browse(integration_id)

        if not integration.is_integration_shopify:
            raise NotImplementedError

        external_template = self.to_external_record(integration)
        return external_template.import_translations(force_import)

    def integration_export_translations(self, integration_id: int, force_export: bool = False):
        integration = self.env['sale.integration'].browse(integration_id)

        if not integration.is_integration_shopify:
            raise NotImplementedError

        external_template = self.to_external_record(integration)
        return external_template.push_translations(force_export)

    def _job_kwargs_export_template_translations(self, integration_id: int):
        integration = self.env['sale.integration'].browse(integration_id)
        return {
            'priority': 18,
            'identity_key': f'export_translations-{integration_id}-{self}',
            'description': f'{integration.name}: Export Translations for the Product "{self.display_name}"',
        }

    def _job_kwargs_import_template_translations(self, integration_id: int):
        integration = self.env['sale.integration'].browse(integration_id)
        return {
            'priority': 19,
            'identity_key': f'import_translations-{integration_id}-{self}',
            'description': f'{integration.name}: Import Translations for the Product "{self.display_name}"',
        }

    def to_images_export_format(self, integration: 'models.Model'):
        if integration.is_integration_shopify:
            if not self._perform_shopify_images_migration(integration):
                # If something happened - drop all maggings and perform export from the scratch
                external_template = self.to_external_record(integration)
                external_template.all_image_external_ids.unlink()

        return super().to_images_export_format(integration)

    def _perform_shopify_images_migration(self, integration: 'models.Model'):
        """Migration of the Shopify images gids from <ProductImage> to <MediaImage>"""
        external_template = self.to_external_record(integration)
        external_images = external_template.all_image_external_ids.filtered('code')

        if any((PRODUCT_IMAGE_CODE_PREFIX in x.code) for x in external_images):
            adapter = integration.adapter

            # Get credentials
            headers = adapter._graphql.headers
            url = adapter._graphql._site.rsplit('/', 1)[0] + f'/2025-10/products/{external_template.code}/images.json'

            # Make a request to get the images
            try:
                response = requests.get(url, params={'fields': 'id,admin_graphql_api_id'}, headers=headers)
            except Exception as ex:
                _logger.error(ex)
                return False

            if not response.ok:
                _logger.error(response.text)
                return False

            try:
                mappings = {
                    str(x['id']): x['admin_graphql_api_id'] for x in response.json()['images']
                }
            except Exception as ex:
                _logger.error(ex)
                return False

            # Update codes
            for record in external_images.filtered(lambda x: PRODUCT_IMAGE_CODE_PREFIX in x.code):
                code = record.code.rsplit('/', 1)[-1]
                if code in mappings:
                    record.code = mappings[code]

        return True
