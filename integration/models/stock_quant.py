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

        # In Odoo, when updating the quantity, the onchange method is triggered and the quantity
        # is updated via the write method. When updating the quantity from Ventor, it is impossible
        # to trigger the onchange method, so a new quant is created and Odoo further combines the
        # same quants into one. Using the "from_ventor" check, we exclude double sending of the
        # stock to the e-commerce system. In future, stock will be sent to their write() method.
        if not records_.env.context.get('from_ventor'):
            records_.trigger_export()

        return records

    def write(self, vals):
        result = super(StockQuant, self).write(vals)

        # To correctly send a qty to the e-commerce system when changing qty in Ventor PRO,
        # it is necessary to separate logic into a separate block, since the requests in
        # the app differ from the standard ones in Odoo
        context = self.env.context
        if context.get('from_ventor'):
            # Sending stock during inventory to Instant Inventory и Inventory Adjustment menus in Ventor PRO
            if TRACKABLE_FIELDS.intersection(set(vals.keys())):
                self.trigger_export()

            # Sending stock by moving products in Internal Transfer menu in Ventor
            if not context.get('button_validate_picking_ids'):
                return result

        if TRACKABLE_FIELDS.intersection(set(vals.keys())):
            self.trigger_export()

        return result

    def unlink(self):
        # Handle mainly an _unlink_zero_quants() case and other deletion cases
        self.trigger_export()
        return super(StockQuant, self).unlink()

    def trigger_export(self):
        if self.env.context.get('skip_inventory_export'):
            return

        _integrations = self.env['sale.integration'].get_integrations('export_inventory')
        if not _integrations:
            return

        templates = self._get_templates_to_export_inventory()

        for template in templates:
            if template.company_id:
                integrations = _integrations.filtered(lambda x: x.company_id == template.company_id)
            else:
                integrations = _integrations

            for integration in integrations:
                template._export_inventory_on_template(integration.id)

    def _get_templates_to_export_inventory(self):
        templates = self.env['product.template']

        for rec in self:
            product = rec.product_id
            templates |= product.product_tmpl_id
            templates |= product.get_bom_parent_templates_recursively()

        return templates.filtered(lambda x: x.integration_should_export_inventory)
