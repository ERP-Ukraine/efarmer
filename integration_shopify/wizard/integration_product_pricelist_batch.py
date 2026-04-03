# See LICENSE file for full copyright and licensing details.

import json
import itertools

from odoo import models, fields


EMPTY_BATCH_PATTERN = """
<div class="alert alert-info">
  <h5><i class="fa fa-info-circle"></i> Catalog Sync Actions</h5>
  <p>
    This batch includes only <strong>catalog inclusion/exclusion actions</strong> for products.
    No price updates were detected in this batch.
  </p>
  <p>
    Products are included in the catalog if they have an active price rule in the mapped Odoo pricelist.
    If no such rule is found, the product is excluded from the Shopify catalog.
  </p>
  <p class="mb-0">
    These changes help ensure that only priced products appear in your store catalog.
    You can review product pricing in the linked <strong>Odoo pricelist</strong> to adjust catalog visibility.
  </p>
</div>
"""

BATCH_TABLE_PATTERN = """
<table class="table table-sm o_list_view">
  <thead>
    <tr>
      <th class="o_column_sortable">Product</th>
      <th class="o_column_sortable">Price</th>
      <th class="o_column_sortable">Compare at price</th>
    </tr>
  </thead>
  <tbody>
    %s
  </tbody>
</table>
"""


class IntegrationProductPricelistBatch(models.TransientModel):
    _name = 'integration.product.pricelist.batch'
    _description = 'Temporary storage of calculated product prices before export to Shopify system'
    _transient_max_hours = 24 * 3
    _order = 'id ASC'

    job_id = fields.Many2one(
        comodel_name='queue.job',
        string='Job',
    )

    state = fields.Selection(
        related='job_id.state',
    )

    catalog_external_line_id = fields.Many2one(
        comodel_name='integration.catalog.external.line',
        string='Catalog External Line',
        required=True,
        ondelete='cascade',
        help='The catalog external line associated with this price calculation.'
    )

    integration_id = fields.Many2one(
        related='catalog_external_line_id.integration_id',
        store=True,
    )

    catalog_id = fields.Many2one(
        related='catalog_external_line_id.catalog_id',
    )

    pricelist_id = fields.Many2one(
        related='catalog_external_line_id.pricelist_id',
    )

    pricelist_compare_at_id = fields.Many2one(
        related='catalog_external_line_id.pricelist_compare_at_id',
    )

    company_id = fields.Many2one(
        related='integration_id.company_id',
    )

    prices_data = fields.Text(
        string='Prices Data',
    )

    publication_data = fields.Text(
        string='Publication Data',
    )

    batch_count = fields.Integer(
        string='Batch Count',
    )

    batch_number = fields.Integer(
        string='Batch Number',
    )

    batch = fields.Char(
        string='Batch',
        compute='_compute_batch',
    )

    def _compute_batch(self):
        for record in self:
            record.batch = f'{record.batch_number} / {record.batch_count}'

    @property
    def catalog_name(self):
        return self.catalog_external_line_id.display_name

    @property
    def prices_data_dict(self):
        data = self.prices_data
        if data:
            return json.loads(data)
        return {}

    @property
    def publication_data_dict(self):
        data = self.publication_data
        if data:
            return json.loads(data)
        return {}

    def create_job(self):
        self.ensure_one()

        job_kwargs = self._job_kwargs_export_pricelist_batch()

        job = self \
            .with_context(company_id=self.company_id.id) \
            .with_delay(**job_kwargs) \
            .export_prices()

        job_log = self.job_log(job)

        self.job_id = job_log.job_id.id

        return job_log

    def action_open_job(self):
        self.ensure_one()
        return self.job_id.get_formview_action()

    def action_active_prices_report(self):
        list_ = [record._format_as_table() for record in self]

        if not any(list_):
            html_text = EMPTY_BATCH_PATTERN
        else:
            html_text = BATCH_TABLE_PATTERN % ''.join(itertools.chain(*list_))

        action = self.env['message.wizard'].create_html_and_run(html_text)
        action['name'] = f'Batch Details: {self.catalog_name}'

        return action

    def export_prices(self):
        self.ensure_one()

        if not self.integration_id.is_integration_shopify:
            raise NotImplementedError

        prices, deleted_products = self._export_prices()
        publicatins_to_include, publicatins_to_exclude = self._export_publications()

        return {
            'ADDED_PRICES': prices,
            'DELETED_VARIANT_PRICES': deleted_products,
            'PUBLICATIONS_TO_INCLUDE': publicatins_to_include,
            'PUBLICATIONS_TO_EXCLUDE': publicatins_to_exclude,
        }

    def _export_prices(self):
        prices_data = self.prices_data
        if not prices_data:
            return False, False

        data = self.prices_data_dict
        pricelist = self.catalog_external_line_id.init_pricelist()  # GQL PriceList class

        prices, deleted_products = pricelist.update_fixed_prices(
            prices_to_add=data['prices_to_add'],
            variant_ids_to_delete=data['variant_ids_to_delete'],
        )

        return [x.to_dict() for x in prices], deleted_products

    def _export_publications(self):
        publication_data = self.publication_data
        if not publication_data:
            return False, False

        data = self.publication_data_dict
        publication = self.catalog_external_line_id.init_publication()  # GQL Publication class

        product_ids_to_include = data['product_ids_to_include']
        product_ids_to_exclude = data['product_ids_to_exclude']

        publication.update(
            product_ids_to_include=product_ids_to_include,
            product_ids_to_exclude=product_ids_to_exclude,
        )

        return product_ids_to_include, product_ids_to_exclude

    def _format_as_table(self):
        data = self.prices_data_dict.get('prices_to_add', [])
        base_url = self.integration_id.get_base_url_config()
        variant_action_id = self.env.ref('product.product_normal_action').id

        list_ = []
        for _, price, compare_at_price, variant_id, name in data:
            href = f'{base_url}/odoo/action-{variant_action_id}/{variant_id}'
            list_.append(
                f'<tr><td><a href="{href}" target="_blank">(id={variant_id}) {name}</a></td>'
                f'<td>{price}</td><td>{compare_at_price}</td></tr>'
            )

        return list_

    def _get_integration_id_for_job(self):
        return self.integration_id.id

    def _job_kwargs_export_pricelist_batch(self):
        i_name = self.integration_id.name
        c_name = self.catalog_name
        p_name = self.pricelist_id.name
        code = self.pricelist_id.currency_code
        identity_key = f'{self.catalog_external_line_id.id}-{self.batch_number}-{self.batch_count}'

        return {
            'priority': 12,
            'identity_key': f'integration_export_prices-{identity_key}',
            'description': (
                f'{i_name}:  Export to catalog "{c_name}" based on pricelist "{p_name}" (Currency: {code}). '
                f'Batch: {self.batch}'
            ),
        }
