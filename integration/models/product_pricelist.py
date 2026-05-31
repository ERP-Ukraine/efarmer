# See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import api, models, fields, _
from odoo.exceptions import UserError, ValidationError

from ..tools import IS_FALSE


FIXED = 'fixed'
FORMULA = 'formula'
PERCENTAGE = 'percentage'


class ProductPricelist(models.Model):
    _name = 'product.pricelist'
    _inherit = ['product.pricelist', 'integration.model.mixin']
    _internal_reference_field = 'name'

    currency_code = fields.Char(
        related='currency_id.name',
        string='Currency Code',
    )

    def trigger_force_export(self):
        price_mapping_ids = self.env['integration.product.pricelist.mapping'].search([
            ('pricelist_id', 'in', self.ids),
            ('integration_id.state', '=', 'active'),
        ])
        if not price_mapping_ids:
            raise UserError(self._integration_not_mapped_error())

        for integration in price_mapping_ids.mapped('integration_id'):
            map_ids = price_mapping_ids.filtered(lambda x: x.integration_id == integration)
            pricelist_ids = map_ids.mapped('pricelist_id')

            job_kwargs = integration._job_kwargs_prepare_specific_prices(pricelist_ids)

            context = {
                'company_id': integration.company_id.id,
                'job_integration_id': integration.id,
                'job_integration_job_type': 'pricelist',
            }
            integration \
                .with_context(**context) \
                .with_delay(**job_kwargs) \
                .export_pricelists_multi(pricelist_ids=pricelist_ids.ids)

        return self._return_display_notification()

    def trigger_update_items_to_external(self, integration_id=False):
        domain = [
            ('pricelist_id', 'in', self.ids),
            ('integration_id.state', '=', 'active'),
        ]
        if integration_id:
            domain.append(('integration_id', '=', integration_id))

        price_mapping_ids = self.env['integration.product.pricelist.mapping'].search(domain)

        if not price_mapping_ids:
            message = self._integration_not_mapped_error()
            if integration_id:
                return message
            raise UserError(message)

        message_list = list()
        value = fields.Datetime.now()

        for integration in price_mapping_ids.mapped('integration_id'):
            force_sync_pricelist = False
            date_point = integration.last_update_pricelist_items
            map_ids = price_mapping_ids.filtered(lambda x: x.integration_id == integration)
            active_pricelist_ids = map_ids.mapped('pricelist_id').filtered('active').ids

            all_item_ids = self.env['product.pricelist.item'].search([
                ('write_date', '>=', date_point),
                ('pricelist_id', 'in', active_pricelist_ids),
            ])

            # Skip previously imported items
            current_integration_id = integration.id
            cursor = self.env.cr

            newly_created = all_item_ids.filtered(
                lambda r: r.create_date == r.write_date
            )

            if newly_created:
                cursor.execute("""
                    SELECT item_id FROM integration_product_pricelist_item_external
                    WHERE integration_id = %s AND item_id IN %s
                """, (current_integration_id, tuple(newly_created.ids)))
                imported_ids = {row[0] for row in cursor.fetchall()}
            else:
                imported_ids = set()

            item_ids = all_item_ids - newly_created.browse(imported_ids)

            if not item_ids:
                # If not any changed items, try to find at least one product template
                # marked as `Force Update Pricelists` (to_force_sync_pricelist = true),
                # because maybe some of the items were deleted.
                query = """
                    SELECT COUNT(p.id) FROM integration_product_template_mapping AS m
                    JOIN product_template as p
                        ON m.integration_id = %s
                        AND m.template_id = p.id
                        AND p.to_force_sync_pricelist = true
                        AND p.exclude_from_synchronization = false
                """

                self.env.cr.execute(query, (current_integration_id,))
                select = self.env.cr.fetchone()
                force_sync_pricelist = select and select[0]

            integration.update_last_update_pricelist_items_to_now(value)

            if not item_ids and not force_sync_pricelist:
                continue

            # Create jobs
            pricelist_ids = item_ids.mapped('pricelist_id')
            job_kwargs = integration._job_kwargs_prepare_specific_prices(pricelist_ids)

            context = {
                'company_id': integration.company_id.id,
                'job_integration_id': integration.id,
                'job_integration_job_type': 'pricelist',
            }
            job = integration \
                .with_context(**context) \
                .with_delay(**job_kwargs) \
                .export_pricelists_multi(item_ids=item_ids.ids, updating=True)

            message_list.append(
                _('%s: Find Products for Specific Prices job created: %s') % (integration.name, job)
            )

        if integration_id:
            message = '\n'.join(message_list) or self._integration_no_need_message()
            return self._return_display_notification(message)

        if not message_list:
            message = self._integration_no_need_message()
            return self._return_display_notification(message)

        return self._return_display_notification()

    def _get_applicable_rules_domain(self, products, date, **kwargs):
        if not self.env.context.get('skip_pricelist_date_validation'):
            return super(ProductPricelist, self)._get_applicable_rules_domain(products, date, **kwargs)

        # All the code below is the implementation of the super method
        # The only change was made -- remove date_start from domain to send pricelist if date_start > today
        self and self.ensure_one()
        if products._name == 'product.template':
            templates_domain = ('product_tmpl_id', 'in', products.ids)
            products_domain = ('product_id.product_tmpl_id', 'in', products.ids)
        else:
            templates_domain = ('product_tmpl_id', 'in', products.product_tmpl_id.ids)
            products_domain = ('product_id', 'in', products.ids)

        return [
            ('pricelist_id', '=', self.id),
            '|', ('categ_id', '=', False), ('categ_id', 'parent_of', products.categ_id.ids),
            '|', ('product_tmpl_id', '=', False), templates_domain,
            '|', ('product_id', '=', False), products_domain,
            '|', ('date_end', '=', False), ('date_end', '>=', date),
        ]

    def _create_integration_items(self, integration, key_tuple, item_list):
        template_external_id, variant_external_id = key_tuple

        if variant_external_id == IS_FALSE:
            external_id = template_external_id
            Mapping = self.env['integration.product.template.mapping']
        else:
            external_id = f'{template_external_id}-{variant_external_id}'
            Mapping = self.env['integration.product.product.mapping']

        tax_include = integration.price_including_taxes
        product_id = Mapping.to_odoo(integration, external_id)  # `template` or `variant`
        product_item_ids = product_id._search_pricelist_items(p_ids=self.ids)

        # 1. Force unlink existing product items
        product_item_ids.with_context(skip_mark_template_to_force_sync=True).unlink()

        # 2. Prepare and create items
        PricelistItem = self.env['product.pricelist.item']
        item_ids = PricelistItem.browse()
        PricelistItemExternal = self.env['integration.product.pricelist.item.external']

        for external_item in item_list:
            vals = self._prepare_item_vals_from_external(product_id, external_item, tax_include)
            item_id = PricelistItem.create(vals)
            item_ids |= item_id

            # 2.1 Create external-item mapping
            item_vals = dict(
                item_id=item_id.id,
                integration_id=integration.id,
                external_item_id=external_item['id'],
                variant_id=(product_id._name == 'product.product' and product_id.id),
                template_id=(product_id._name == 'product.template' and product_id.id),
            )
            PricelistItemExternal.create(item_vals)

        return item_ids

    def _prepare_item_vals_from_external(self, product, item, tax_include):
        if product._name == 'product.template':
            _vals = dict(
                product_id=False,
                applied_on='1_product',
                product_tmpl_id=product.id,
            )
        else:
            _vals = dict(
                product_id=product.id,
                applied_on='0_product_variant',
                product_tmpl_id=product.product_tmpl_id.id,
            )

        vals = dict(
            pricelist_id=self.id,
            date_end=item['date_end'],
            date_start=item['date_start'],
            min_quantity=item['min_quantity'],
            **_vals,
        )

        fixed_price = item['fixed_price']
        reduction = item['reduction']
        reduction_type = (FIXED, PERCENTAGE)[item['reduction_type'] == PERCENTAGE]

        if reduction and reduction_type == PERCENTAGE:
            vals.update(
                percent_price=reduction * 100,
                compute_price=PERCENTAGE,
            )
        elif reduction and reduction_type == FIXED:
            value = reduction
            reduction_tax_included = item['reduction_tax_included']

            if tax_include != reduction_tax_included:
                res = product.taxes_id.compute_all(  # I'm not sure about that
                    reduction,
                    product=product,
                    partner=self.env['res.partner'],
                )

                if tax_include and not reduction_tax_included:
                    value = res['total_included']
                elif not tax_include and reduction_tax_included:
                    value = res['total_excluded']

            vals.update(
                price_surcharge=-value,
                compute_price=FORMULA,
            )
        elif fixed_price:
            vals.update(
                fixed_price=fixed_price,
                compute_price=FIXED,
            )
        else:
            raise ValidationError(_(
                'Unsupported pricelist configuration detected for product "%s".\n\n'
                'Details of the issue:\n'
                '- Product ID: %s\n'
                '- Item details: %s\n\n'
                'Please check the product and pricelist configuration and ensure that valid price or '
                'reduction data is provided.'
            ) % (product.display_name, product.id, item))

        return vals

    def _job_kwargs_create_pricelist_items(self, integration, external_id):
        complex_id = f'{integration.id}-{self.id}-{external_id}'
        complex_name = f'"{self.name}" (external={external_id})'
        return {
            'priority': 18,
            'identity_key': f'create_pricelist_items-{complex_id}',
            'description': f'{integration.name}: Create Pricelist Items in Odoo for {complex_name}',
        }

    @staticmethod
    def _integration_not_mapped_error():
        return _(
            'No active integrations or mapped pricelists were found. Please ensure that an integration is '
            'active and pricelists are correctly mapped.'
        )

    @staticmethod
    def _integration_no_need_message():
        return _('Operation skipped. No pricelist items were found for export.')

    def _return_display_notification(self, msg=False):
        message = msg or _('Queue Jobs "Find Products for Specific Prices" were created')
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Find Products for Specific Prices'),
                'message': message,
                'type': 'success',
                'sticky': False,
            }
        }


class ProductPricelistItem(models.Model):
    _inherit = 'product.pricelist.item'

    @property
    def is_applied_on_product(self):
        return self.applied_on in ('1_product', '0_product_variant')

    def _get_applied_on_template(self):
        if self.applied_on == '1_product':
            return self.product_tmpl_id
        elif self.applied_on == '0_product_variant':
            return self.product_id.product_tmpl_id
        return self.env['product.template']

    @api.model_create_multi
    def create(self, vals_list):
        records = super(ProductPricelistItem, self.with_context(skip_product_export=True)) \
            .create(vals_list)

        if self.env.context.get('skip_product_export') or self.env.context.get('skip_mark_template_to_force_sync'):
            return records

        records.trigger_integration_products_export()

        return records

    def write(self, values):
        res = super().write(values)

        if self.env.context.get('skip_product_export') or self.env.context.get('skip_mark_template_to_force_sync'):
            return res

        self.trigger_integration_products_export()

        return res

    def unlink(self):
        if not self.env.context.get('skip_mark_template_to_force_sync'):
            for rec in self:
                rec._mark_template_to_force_sync()

            if not self.env.context.get('skip_product_export'):
                self.trigger_integration_products_export()

        return super(ProductPricelistItem, self).unlink()

    def trigger_integration_products_export(self):
        integrations = self.env['sale.integration'] \
            .get_integrations('export_template') \
            .filtered(lambda x: x.integration_pricelist_id or x.integration_sale_pricelist_id)

        if not integrations:
            return False

        data = defaultdict(set)

        # 1. Collect data dictionary
        for rec in self:
            if not rec.is_applied_on_product:
                continue

            template = rec._get_applied_on_template()
            if not template.product_variant_ids or template.exclude_from_synchronization:
                continue

            template_integrations = template._get_enabled_integrations()

            for integration in integrations:
                if integration not in template_integrations:
                    continue

                pricelist_ids = [
                    integration.integration_pricelist_id.id,
                    integration.integration_sale_pricelist_id.id,
                ]

                if rec.pricelist_id.id in pricelist_ids:
                    data[integration].add(template)

        # 2. Process data dictionary (trigger template export)
        for integration, template_set in data.items():
            integration = integration.with_context(company_id=integration.company_id.id)

            for template in template_set:
                job_kwargs = integration._job_kwargs_export_template(template, False)
                context = {
                    'company_id': integration.company_id.id,
                    'job_integration_id': integration.id,
                    'job_integration_job_type': 'product',
                    'job_template_id': template.id,
                }
                integration.with_context(**context).with_delay(**job_kwargs).export_template(template)

    def to_export_format(self, integration: 'models.Model', res_model, raise_error=False):
        is_valid, error = self._validate_for_integration_export()

        if not is_valid:
            if raise_error:
                raise ValidationError(error)
            vals = dict(_is_valid=is_valid, _item_id=self.id, _error=error)
            return vals

        pricelist_id = self.pricelist_id
        external_pricelist_id = pricelist_id.to_external_record(integration)

        price = self._get_price_value_for_integration()
        external_item_ids = self.get_external_item_ids(res_model, integration.id)

        vals = {
            '_error': error,
            '_item_id': self.id,
            '_is_valid': is_valid,
            '_external_item_ids': external_item_ids,
            'date_end': self.date_end,
            'date_start': self.date_start,
            'min_quantity': int(self.min_quantity),
            'external_name': external_pricelist_id.name,
            'external_group_id': external_pricelist_id.code,
            'price': (int(), price)[self.compute_price == FIXED],
            'reduction': (int(), price)[self.compute_price in (PERCENTAGE, FORMULA)],
            'reduction_type': self._get_reduction_type_for_integration(),
            'reduction_tax_included': integration.price_including_taxes,
        }
        return vals

    def get_external_item_ids(self, res_model, integration_id):
        if res_model == 'product.template':
            tmpl_id, var_id = self.product_tmpl_id.id, False
        else:
            tmpl_id, var_id = False, self.product_id.id

        domain = [
            ('item_id', '=', self.id),
            ('variant_id', '=', var_id),
            ('template_id', '=', tmpl_id),
            ('integration_id', '=', integration_id),
        ]
        records = self.env['integration.product.pricelist.item.external'].search(domain)
        return records.mapped('external_item_id')

    def _get_price_value_for_integration(self):
        price_mapping = {
            FIXED: 'fixed_price',
            PERCENTAGE: 'percent_price',
            FORMULA: ('price_surcharge', 'price_discount'),
        }
        field_name = price_mapping[self.compute_price]

        # In `formula` we are handling or negative `extra fee` or positive `discount`
        if self.compute_price == FORMULA:
            field_name = field_name[(self.price_discount > 0)]

        price = getattr(self, field_name) or int()

        if field_name in ('percent_price', 'price_discount'):
            price = price / 100
        elif field_name == 'price_surcharge':
            price = abs(price)

        return round(price, 4)

    def _get_reduction_type_for_integration(self):
        reduction_mapping = {
            FIXED: 'amount',
            PERCENTAGE: PERCENTAGE,
            FORMULA: ('amount', PERCENTAGE),
        }
        reduction_type = reduction_mapping[self.compute_price]
        # In `formula` we are handling or negative `extra fee` or positive `discount`
        if self.compute_price == FORMULA:
            reduction_type = reduction_type[(self.price_discount > 0)]

        return reduction_type

    def _mark_template_to_force_sync(self):
        if self.is_applied_on_product:
            template = self._get_applied_on_template()
            if not template:
                return False
            condition = 'id = %s'
            params = (template.id,)
        elif self.applied_on == '2_product_category':
            if not self.categ_id:
                return False
            condition = 'categ_id = %s'
            params = (self.categ_id.id,)
        elif self.applied_on == '3_global':
            condition = ''
            params = ()
        else:
            return False

        query = 'UPDATE product_template SET to_force_sync_pricelist = true'
        if condition:
            query = f'{query} WHERE {condition}'

        self.env.cr.execute(query, params)

        return True

    def _validate_for_integration_export(self):
        error = str()
        is_valid = True

        # If not formula-based, return early as it's valid
        if self.compute_price != FORMULA:
            return is_valid, error

        # Check conditions specific to formula-based pricelist items
        if self.base != 'list_price':
            is_valid = False
            error = _('Formula is based on "%s", which is not supported for export.') % self.base
        elif self.price_min_margin:
            is_valid = False
            error = _('Pricelist margin in formula is not supported for export.')
        elif self.price_surcharge > 0:
            is_valid = False
            error = _('Positive "Extra Fee" in the formula is not supported for export.')
        elif self.price_surcharge and self.price_discount:
            is_valid = False
            error = _('"Extra Fee" and "Price Discount" may not be handled together.')
        elif not self.price_surcharge and not self.price_discount:
            is_valid = False
            error = _('Neither "Extra Fee" nor "Price Discount" is specified in the formula.')

        # Construct a detailed error message if validation fails
        if error:
            error = _(
                'Pricelist: "%s" (ID: %s).\n'
                'Item: "%s" (ID: %s).\n'
                'Error: %s'
            ) % (
                self.pricelist_id.display_name,
                self.pricelist_id.id,
                self.display_name,
                self.id,
                error,
            )

        return is_valid, error
