# See LICENSE file for full copyright and licensing details.

from odoo import models, _


class IntegrationProductPricelistExternal(models.Model):
    _name = 'integration.product.pricelist.external'
    _inherit = 'integration.external.mixin'
    _description = 'Integration Product Pricelist External'
    _odoo_model = 'product.pricelist'

    def import_special_prices_external(self):
        integration = self.integration_id
        adapter = integration.adapter
        external_codes_read = self.env['integration.product.template.external'].search_read(
            domain=[('integration_id', '=', integration.id)],
            fields=['code'],
        )
        external_codes = {x['code'] for x in external_codes_read}

        params = dict(id_group=self.code)
        external_data = adapter.get_special_prices(external_codes, **params)
        if not external_data:
            return _('Special prices for External Group "%s" not found.') % self.name

        pricelist = self.mapping_model.to_odoo(integration, self.code)
        pricelist = pricelist.with_context(
            company_id=integration.company_id.id,
            default_integration_id=integration.id,
        )

        result = list()
        for (template_id, variant_id), item_list in external_data.items():
            job_kwargs = pricelist._job_kwargs_create_pricelist_items(
                integration,
                f'{template_id}-{variant_id}',
            )
            job = pricelist\
                .with_delay(**job_kwargs) \
                ._create_integration_items(
                    integration,
                    (template_id, variant_id),
                    item_list,
                )

            pricelist.job_log(job)
            result.append(job)

        return result

    def import_special_prices_external_product(self, external_product_id, **kw):  # Just for Debug
        integration = self.integration_id
        adapter = integration.adapter

        params = dict(id_group=self.code, id_product=external_product_id)
        params.update(kw)

        external_data = adapter.get_special_prices([], **params)
        if not external_data:
            return _('Special prices for External Group "%s" not found.') % self.name

        pricelist = self.mapping_model.to_odoo(integration, self.code)

        result = list()
        for (template_id, variant_id), item_list in external_data.items():
            items = pricelist._create_integration_items(
                integration,
                (template_id, variant_id),
                item_list,
            )

            result.append(
                (f'{template_id}-{variant_id}', items.ids)
            )

        return result

    def _fix_unmapped(self, adapter_external_data):
        result = list()
        mapping_model = self.mapping_model

        for record, adapter_data in zip(self, adapter_external_data):
            mapping = mapping_model.search([
                ('external_pricelist_id', '=', record.id),
                ('integration_id', '=', record.integration_id.id),
            ], limit=1)

            if not mapping:
                continue

            odoo_record = mapping._fix_unmapped_pricelist_one(external_data=adapter_data)
            result.append(odoo_record)

        return result

    def _job_kwargs_import_special_prices(self, pricelist_id):
        complex_id = f'{self.integration_id.id}-{self.id}-{pricelist_id.id}'
        complex_name = f'{self.name} → {pricelist_id.name}'
        return {
            'identity_key': f'import_special_prices-{complex_id}',
            'description': f'{self.integration_id.name}: Import Specific prices "{complex_name}"',
        }
