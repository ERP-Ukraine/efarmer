# See LICENSE file for full copyright and licensing details.

from odoo import api, models


TRACKABLE_FIELDS = {
    'lot_id',
    'quantity',
    'reserved_quantity',
    'location_id',
}


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    @api.model_create_multi
    def create(self, vals_list):
        # Original create() method calls write() method which triggers inventory export.
        # We will trigger inventory export manually later, this is why we pass flag to disable
        # running export on create().

        self_ = self.with_context(skip_inventory_export=True)
        records = super(StockQuant, self_).create(vals_list)

        records_ = records.with_context(skip_inventory_export=False)
        records_.trigger_export()

        return records

    def write(self, vals):
        result = super(StockQuant, self).write(vals)

        if TRACKABLE_FIELDS.intersection(set(vals.keys())):
            self.trigger_export()

        return result

    def trigger_export(self):
        if self.env.context.get('skip_inventory_export'):
            return

        integrations = self.env['sale.integration'].get_integrations('export_inventory')
        if not integrations:
            return

        templates = self._get_templates_to_export_inventory()

        for template in templates:
            if template.company_id:
                integrations = integrations.filtered(lambda x: x.company_id == template.company_id)

            for integration in integrations:
                template._export_inventory_on_template(integration)

    def _get_templates_to_export_inventory(self):
        templates = self.env['product.template']

        for rec in self:
            product = rec.product_id
            templates |= product.product_tmpl_id
            templates |= product.get_used_in_kits_recursively()

        return templates.filtered(
            lambda x: x.type == 'product'
            and not x.exclude_from_synchronization
            and not x.exclude_from_synchronization_stock
        )
