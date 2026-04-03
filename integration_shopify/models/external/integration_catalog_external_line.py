# See LICENSE file for full copyright and licensing details.

import json

from odoo import models, fields, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_round

from ...shopify.connection import _SHOPIFY_BATCH_LIMIT as LIMIT


class IntegrationCatalogExternalLine(models.Model):
    _name = 'integration.catalog.external.line'
    _description = 'Integration Catalog External Line'

    integration_id = fields.Many2one(
        comodel_name='sale.integration',
        string='E-Commerce Store',
        ondelete='cascade',
        required=True,
    )

    catalog_id = fields.Many2one(
        comodel_name='integration.catalog.external',
        string='Catalog',
    )

    pricelist_id = fields.Many2one(
        comodel_name='product.pricelist',
        string='Pricelist',
    )

    pricelist_compare_at_id = fields.Many2one(
        comodel_name='product.pricelist',
        string='Pricelist Compare At',
    )

    currency_code = fields.Char(
        related='catalog_id.currency_code',
    )

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f'{rec.catalog_id.name} [{rec.currency_code}]'

    def init_pricelist(self):
        self.ensure_one()
        integration = self.integration_id

        if integration.is_integration_shopify:
            pricelist_data = self.catalog_id.pricelist_data_dict

            if not pricelist_data:
                raise UserError(
                    _('%s: Pricelist data not found for the: "%s" catalog.')
                    % (integration.name, self.catalog_id.name)
                )

            return integration.adapter.gql.PriceList.set(**pricelist_data)

        raise NotImplementedError

    def init_publication(self):
        self.ensure_one()
        integration = self.integration_id

        if integration.is_integration_shopify:
            publication_data = self.catalog_id.publication_data_dict

            if not publication_data:
                raise UserError(
                    _('%s: Publication data not found for the: "%s" catalog.')
                    % (integration.name, self.catalog_id.name)
                )

            return integration.adapter.gql.Publication.set(**publication_data)

        raise NotImplementedError

    def action_create_preview_price_batches(self):
        self.ensure_one()

        items = self.create_price_batches(run_export=False)

        action = self.sudo().env.ref(
            'integration_shopify.integration_product_pricelist_batch_action').read()[0]
        action['domain'] = [('id', 'in', items.ids)]

        return action

    def create_price_batches_with_delay(self):
        self.ensure_one()

        job_kwargs = self._job_kwargs_create_price_batches()
        job = self.with_delay(**job_kwargs).create_price_batches()

        self.job_log(job)

        return job

    def create_price_batches(self, run_export: bool = True):
        self.ensure_one()

        # 1. Remove old calculations with sql query
        self.integration_id._unlink_product_pricelist_batches()

        # 2. Select pairs of external and odoo products
        record_list = self.integration_id._get_pairs_of_external_and_odoo_products()

        items = self.env['integration.product.pricelist.batch']

        #  3. Split record_list by 250 rows per iteration
        list_len = len(record_list)
        batch_count = (list_len + LIMIT - 1) // LIMIT

        for idx, batch in enumerate((record_list[i:i + LIMIT] for i in range(0, list_len, LIMIT))):
            prices_to_add, variant_to_delete, product_to_include, product_to_exclude = [], [], set(), set()

            for variant_code, variant_id in batch:
                variant = self.env['product.product'].browse(variant_id)
                external_template_id, external_variant_id = variant_code.split('-')

                price, compare_at_price = self._prepare_prices(variant)

                if price is None:
                    variant_to_delete.append(external_variant_id)
                    product_to_exclude.add(external_template_id)
                    continue

                prices_to_add.append(
                    (external_variant_id, price, compare_at_price, variant_id, variant.display_name)
                )
                product_to_include.add(external_template_id)

            # 4. Create batch if there are any changes
            if prices_to_add or variant_to_delete or product_to_include or product_to_exclude:
                item = self.env['integration.product.pricelist.batch'].create({
                    'catalog_external_line_id': self.id,
                    'prices_data': json.dumps({
                        'prices_to_add': prices_to_add,
                        'variant_ids_to_delete': variant_to_delete,
                    }),
                    'publication_data': json.dumps({
                        'product_ids_to_include': list(product_to_include),
                        'product_ids_to_exclude': list(product_to_exclude),
                    }),
                    'state': False if run_export else 'cancelled',
                    'batch_number': idx + 1,
                    'batch_count': batch_count,
                })

                #  4.1. Create queue.job for export
                if run_export:
                    item.create_job()

                items |= item

        return items

    def _prepare_prices(self, variant: 'models.Model'):
        price, rule = self.pricelist_id._get_product_price_rule(variant, 0)

        if not rule:
            return None, None

        pricelist_compare_at = self.pricelist_compare_at_id
        if pricelist_compare_at:
            compare_at_price, rule = pricelist_compare_at._get_product_price_rule(variant, 0)

            if not rule:
                compare_at_price = None
        else:
            compare_at_price = None

        return self._round_price(price), self._round_price(compare_at_price)

    def _round_price(self, price: float):
        if not isinstance(price, float):
            return price

        return float_round(
            value=price,
            precision_digits=self.env['decimal.precision'].precision_get('Product Price'),
        )

    def _get_integration_id_for_job(self):
        return self.integration_id.id

    def _job_kwargs_create_price_batches(self):
        i_name = self.integration_id.name
        c_name = self.catalog_id.name
        p_name = self.pricelist_id.name
        code = self.pricelist_id.currency_code

        return {
            'priority': 12,
            'identity_key': f'integration_create_price_batches-{self.id}',
            'description': f'{i_name}: Prepare catalog "{c_name}" data from pricelist "{p_name}" (Currency: {code})',
        }
