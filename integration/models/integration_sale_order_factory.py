# See LICENSE file for full copyright and licensing details.

import json
from typing import Dict

from odoo import fields, models, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_is_zero, float_round
from odoo.tools.translate import LazyTranslate

from ..exceptions import ErrorStore, ApiImportError, NotMappedFromExternal


_lt = LazyTranslate(__name__)


# Mark strings for extraction (never executed, just for translation tools)
_lt('Discount for %s')
_lt('Coupon: %s')


class IntegrationSaleOrderFactory(models.TransientModel):
    _name = 'integration.sale.order.factory'
    _description = 'Integration Sale Order Factory'

    input_file_id = fields.Many2one(
        comodel_name='sale.integration.input.file',
        string='Input File',
        required=True,
        ondelete='cascade',
    )

    integration_id = fields.Many2one(
        comodel_name='sale.integration',
        string='E-Commerce Store',
        related='input_file_id.si_id',
        store=True,
    )

    raw_data = fields.Text(
        related='input_file_id.raw_data',
    )

    external_order_status = fields.Char(
        string='External Order Status',
    )

    payment_method_code = fields.Char(
        string='Payment Method Code',
    )

    is_cancelled = fields.Boolean(
        string='Is Cancelled',
    )

    @property
    def workflow_states(self):
        return [x for x in [self.external_order_status] if x]

    def create_order(self):
        self.ensure_one()
        order_data = self.input_file_id.parse()
        self.is_cancelled = order_data.pop('is_cancelled', False)
        self._extract_workflow_data(order_data)

        integration = self.integration_id
        order = self.env['integration.sale.order.mapping'].search([
            ('integration_id', '=', integration.id),
            ('external_id.code', '=', order_data['id']),
        ]).odoo_id

        if not order:
            order = self._create_order(order_data)
            order.create_mapping(integration, order_data['id'], extra_vals={'name': order.name})
            self._post_create_order(order, order_data)

        return order

    def _extract_workflow_data(self, order_data):
        """
        Extract workflow-related data from parsed order and store on factory fields.
        Override in connector-specific factories to handle additional workflow states
        (e.g. Shopify's separate financial and fulfillment statuses).
        """
        states = order_data.get('integration_workflow_states', [])
        self.external_order_status = states[0] if states else False
        self.payment_method_code = order_data.get('payment_method')

    def _create_order(self, order_data):
        integration = self.integration_id
        order_vals = self._prepare_order_vals(order_data)

        order_name = self.env['sale.order'] \
            .get_integration_order_name(integration, order_data['ref'])

        if order_name:
            order_vals['name'] = order_name

        order = self.env['sale.order'] \
            .with_context(
                skip_dispatch_to_external=True,
                skip_integration_order_post_action=True,
            ) \
            .create(order_vals)

        # Create order lines
        self._create_order_lines(order, order_data)

        # Additional Order adjustments
        order._apply_values_from_external(order_data)

        # Configure dictionary with the default/force values after `onchange_partner_id()` method
        values = {
            'partner_invoice_id': order_vals['partner_invoice_id'],
            'partner_shipping_id': order_vals['partner_shipping_id'],
        }

        if integration.default_sales_team_id:
            values['team_id'] = integration.default_sales_team_id.id

        if integration.default_sales_person_id:
            values['user_id'] = integration.default_sales_person_id.id
        elif integration.keep_sales_person_empty:
            values['user_id'] = False

        delivery = self.env['res.partner'].browse(order_vals['partner_shipping_id'])

        fiscal_position = self.env['account.fiscal.position'] \
            .with_company(order.company_id) \
            ._get_fiscal_position(order.partner_id, delivery)

        values['fiscal_position_id'] = fiscal_position.id

        # Payment Terms should be set after order is created because after order is created
        # onchange/depends functions are called. And they are changing payment terms
        # and as result they are taken from res.partner. And we have functionality to force set
        # Payment Terms from the payment method
        payment_method = self._get_payment_method(order_data['payment_method'])
        values['payment_method_id'] = payment_method.id
        payment_method_external = payment_method.to_external_record(integration)
        if payment_method_external.payment_term_id:
            values['payment_term_id'] = payment_method_external.payment_term_id.id

        # Processing external order field mapping for an order
        raw_data = json.loads(self.raw_data)
        values.update(self._map_external_order_fields(raw_data))

        order.write(values)

        self._create_order_additional_lines(order, order_data)

        # Recompute taxes based on the fiscal position
        if order.fiscal_position_id:
            if integration.update_fiscal_position:
                order.action_update_taxes()
            else:
                order.show_update_fpos = True

        return order

    def _create_order_lines(self, order, order_data):
        """
        Create order lines after order is created.
        """
        integration = self.integration_id
        lines_to_create = []

        for line in order_data['lines']:
            # Main line
            line_vals = self._prepare_order_line_vals(order, line)
            if line_vals:
                lines_to_create.append((0, 0, line_vals))

            # Separate discount line (if enabled)
            if integration.separate_discount_line:
                discount_line_vals = self._prepare_order_discount_line_vals(order, line)
                if discount_line_vals:
                    lines_to_create.append((0, 0, discount_line_vals))

        # Hook for customizations
        lines_to_create = self._post_create_order_lines(order, order_data, lines_to_create)

        if lines_to_create:
            order.write({'order_line': lines_to_create})

    def _post_create_order_lines(self, order, order_data, lines_to_create):
        """
        Hook called before creating order lines.
        Override this method to modify lines_to_create list before writing.

        :param order: sale.order recordset
        :param order_data: dict with raw order data from e-commerce platform
        :param lines_to_create: list of tuples [(0, 0, vals), ...]
        :return: modified lines_to_create list
        """
        return lines_to_create

    def _create_order_additional_lines(self, order, order_data):
        integration = self.integration_id
        # 1. Creating Delivery Line
        self._create_delivery_line(order, order_data['delivery_data'])

        # 2. Creating Discount Line.
        # !!! It should be after Creating Delivery Line
        self._create_discount_line(order, order_data['discount_data'])  # Prestashop only

        # 3. Creating Gift Wrapping Line
        self._create_gift_line(order, order_data['gift_data'])

        # 4. Check difference of total order amount and correct it
        #    !!! This block must be the last !!!
        if integration.use_order_total_difference_correction:
            if order_data.get('amount_total', False):
                self._create_line_with_price_difference_product(order, order_data['amount_total'])

    def _map_external_order_fields(self, external_order_data) -> Dict:
        """
        Map external order fields to Odoo fields (only active mappings).
        Returns:
            dict: Values for the order.
        """
        integration = self.integration_id
        values = {}

        mappings = integration.external_order_field_mapping_ids.filtered(
            lambda m: m.active and m.odoo_order_field_id
        )

        for mapping in mappings:
            field_name = mapping.odoo_order_field_id.name
            value = mapping.calculate_order_import_value(external_order_data, raise_error=False)

            if value is not None:
                values[field_name] = value

        return values

    def _prepare_order_vals_hook(self, original_order_data, create_order_vals):
        # Use this method to override in subclasses to define different behavior
        # of preparation of order values
        pass

    def _prepare_order_vals(self, order_data):
        """
        Prepare order values for creating a sale order.
        Args:
            order_data: Dictionary containing order data.
        Returns:
            dict: Prepared order values.
        """
        integration = self.integration_id
        PartnerFactory = self.env['integration.res.partner.factory'].create_factory(
            integration.id,
            customer_data=order_data.get('customer', {}),
            billing_data=order_data.get('billing', {}),
            shipping_data=order_data.get('shipping', {}),
        )

        # Get partner and addresses from the partner factory
        partner, addresses = PartnerFactory.get_partner_and_addresses()

        shipping = addresses['shipping']
        billing = addresses['billing']

        order_vals = {
            'integration_id': integration.id,
            'integration_amount_total': order_data.get('amount_total', False),
            'partner_id': partner.id if partner else False,
            'partner_shipping_id': shipping.id if shipping else False,
            'partner_invoice_id': billing.id if billing else False,
            'related_input_files': [(6, 0, self.input_file_id.ids)],
        }

        if integration.so_external_reference_field:
            field_name = integration.so_external_reference_field.name

            if not (integration.use_odoo_so_numbering and field_name == 'name'):
                order_vals[field_name] = order_data['ref']

        if order_data.get('date_order'):
            external_date_converted = integration._set_zero_time_zone(order_data['date_order'])
            order_vals['date_order'] = external_date_converted

        current_state = order_data.get('current_order_state')
        if current_state:
            sub_status = integration._get_order_sub_status(current_state)
            order_vals['sub_status_id'] = sub_status.id

        pricelist = self._get_order_pricelist(order_data.get('currency'), partner=partner)
        if pricelist:
            order_vals['pricelist_id'] = pricelist.id

        self._prepare_order_vals_hook(order_data, order_vals)

        return order_vals

    def _prepare_order_discount_line_vals(self, order, line_data, product=None):
        """
        Prepare order line values for a discount line.

        :param order: sale.order recordset
        :param line_data: dict with raw line data from e-commerce platform
        :param product: product.product recordset (optional)
        :return: dict with prepared order line values for discount line
        """
        integration = self.integration_id
        discount = line_data['discount']
        if not isinstance(discount, dict):
            raise ValueError(_('Expected the dict object for discount data'))

        if not discount or not discount.get('discount_amount'):
            return dict()

        discount_product = integration.discount_product_id
        if not discount_product:
            raise ApiImportError(
                _(
                    'Discount Product is not configured for the "%s" integration.\n'
                    'To resolve this issue, please configure the "Discount Product" setting in '
                    'the "Sales Orders" tab of the integration settings:\n'
                    '1. Go to "E-Commerce Integrations → Stores → %s → Sales Orders" tab.\n'
                    '2. Set the "Discount Product" field.\n\n'
                    'Once this is done, requeue the job to continue processing.'
                ) % (integration.name, integration.name)
            )

        discount_price = discount['discount_amount']

        if not product:
            try:
                product = self._try_get_odoo_product(line_data)
            except (ErrorStore.UndefinedExternalProduct, ErrorStore.NotFoundExternalProduct):
                product = self.env['product.product']

        taxes = self.env['account.tax']
        if not discount.get('discount_skip_taxes', False):
            taxes = self.get_taxes_from_external_list(product, line_data['taxes'])

        if discount.get('discount_amount_tax_incl'):
            if taxes and self._get_tax_price_included(taxes):
                discount_price = discount['discount_amount_tax_incl']

        # Negate the discount price to ensure it's represented as a negative value.
        # This is necessary because discounts are typically negative values in accounting.
        discount_price = discount_price * -1

        # create discount line values dictionary
        if product:
            line_name = product.display_name
        else:
            line_name, line_reference = line_data.get('name'), line_data.get('reference')
            if line_reference:
                line_name = f'[{line_reference}] {line_name}'

        # Prepare discount order line Description in customer language (if available)
        lang = order.partner_id.lang
        if lang:
            product = product.with_context(lang=lang)
            discount_product = discount_product.with_context(lang=lang)

        discount_description = self._get_translated_string('Discount for %s', product.display_name, lang=lang)
        discount_name = self._update_order_description(discount_product, [discount_description])

        vals = {
            'product_id': discount_product.id,
            'name': discount_name,
            'price_unit': discount_price,
            'product_uom_qty': 1,
            'tax_ids': [(6, 0, taxes.ids)],
        }

        return vals

    def _get_order_pricelist(self, order_currency_iso, partner):
        integration = self.integration_id
        company = integration.company_id
        company_currency_iso = company.currency_id.name

        if not company_currency_iso or not order_currency_iso:
            return False

        # Use pricelist from partner if it's set and currency is the same as order currency
        if partner and partner.property_product_pricelist:
            pricelist_currency_iso = partner.property_product_pricelist.currency_id.name

            if pricelist_currency_iso.lower() == order_currency_iso.lower():
                return partner.property_product_pricelist

        # Try to find pricelist by currency
        odoo_currency = self.env['res.currency'].search([
            ('name', '=ilike', order_currency_iso.lower()),
        ], limit=1)
        if not odoo_currency:
            raise ApiImportError(
                _(
                    'Currency with ISO code "%s" was not found in Odoo.\n'
                    'To resolve this issue, please ensure that the currency is correctly configured in Odoo:\n'
                    '1. Go to "Accounting → Configuration → Currencies".\n'
                    '2. Check if the currency "%s" exists, and if not, create it.\n\n'
                    'Once the currency is configured, requeue the job to continue processing.'
                ) % (order_currency_iso.upper(), order_currency_iso.upper())
            )

        Pricelist = self.env['product.pricelist']

        pricelists = Pricelist.search([
            ('company_id', 'in', (company.id, False)),
            ('currency_id', '=', odoo_currency.id),
        ])
        pricelist = pricelists.filtered(lambda x: x.company_id == company)[:1] or pricelists[:1]

        if not pricelist:
            vals = {
                'company_id': company.id,
                'currency_id': odoo_currency.id,
                'name': f'Integration {order_currency_iso}',
            }
            pricelist = Pricelist.create(vals)

        return pricelist

    def _try_get_odoo_product(self, line, force_create=False):
        """
        This method can be used when we need to customize logic of product search/creation for order lines.
        """
        return self.integration_id._try_get_odoo_product(line, force_create=force_create)

    def _prepare_order_line_vals(self, order, line_data):
        """
        Set forcibly discount to zero to avoid affection of the price list
        with policy "Show public price & discount to the customer".
        If necessary, the discount will be created as a separate line.

        :param order: sale.order recordset
        :param line_data: dict with raw line data from e-commerce platform
        :return: dict with prepared order line values
        """
        integration = self.integration_id
        vals = {
            'discount': 0,
            'integration_external_id': line_data['id'],
            'external_location_id': line_data.get('external_location_id', False),
        }

        # If there is coupons or any other additional information from e-commerce system (e.g. add_description_list),
        # we should handle translations by ourselves. Otherwise,
        # we should follow default Odoo implementation (and keep name field empty)
        lang = order.partner_id.lang

        additional_description_data = list(line_data.get('add_description_list') or [])
        coupon = line_data.get('coupon')

        if coupon:
            coupon_description = self._get_translated_string('Coupon: %s', coupon, lang=lang)
            additional_description_data.append(coupon_description)

        try:
            product = self._try_get_odoo_product(line_data)
            vals['product_id'] = product.id
        except (ErrorStore.UndefinedExternalProduct, ErrorStore.NotFoundExternalProduct):
            line_name, line_reference = line_data['name'], line_data['reference']

            # Try to get fallback product if the product is not found or not defined
            product = integration.get_fallback_product_or_raise(
                line_data['product_id'],
                line_name,
                line_reference,
            )
            vals['product_id'] = product.id

            # Add product name to the description list takin into account that
            # the add_description_list variable also may contains some text
            if line_reference:
                line_name = f'[{line_reference}] {line_name}'

            additional_description_data.insert(0, line_name)
            vals['name'] = '\n'.join(additional_description_data)

        if 'product_uom_qty' in line_data:
            vals['product_uom_qty'] = line_data['product_uom_qty']

        taxes = self.get_taxes_from_external_list(product, line_data['taxes'])
        vals['tax_ids'] = [(6, 0, taxes.ids)]

        vals['price_unit'] = line_data['price_unit']
        if taxes and self._get_tax_price_included(taxes):
            if line_data.get('price_unit_tax_incl'):
                vals['price_unit'] = line_data['price_unit_tax_incl']

        # Create discount included in the line
        if not integration.separate_discount_line and line_data.get('discount'):
            vals['discount'] = line_data['discount']['discount_percent']

        # Don't override 'name' if it was already set for a fallback product
        if not vals.get('name') and additional_description_data:
            if lang:
                product = product.with_context(lang=lang)
            vals['name'] = self._update_order_description(product, additional_description_data)

        return vals

    def _update_order_description(self, product, additional_data):
        description = product.get_product_multiline_description_sale()
        if not additional_data:
            return description
        return description + '\n' + '\n'.join(additional_data)

    def get_taxes_from_external_list(self, product, external_tax_ids):
        integration = self.integration_id
        taxes = self.env['account.tax']

        if external_tax_ids:
            for external_tax_id in external_tax_ids:
                taxes |= self.try_get_odoo_tax(external_tax_id)
            return taxes

        policy = integration.behavior_on_empty_tax

        if policy == 'leave_empty':
            pass
        elif policy == 'set_special_tax':
            error = None
            taxes = integration.zero_tax_id

            # Case 1: Special Zero Tax is not specified
            if not taxes:
                error = _(
                    'No "Special Zero Tax" is specified for the "%s" integration.\n\n'
                    'To resolve this issue, please configure the "Special Zero Tax" field in '
                    'the "Sales Orders" tab of the integration settings.'
                ) % integration.name

            # Case 2: Special Zero Tax has a non-zero amount
            elif taxes.amount:
                error = _(
                    'The "Special Zero Tax" specified for the "%s" integration has a non-zero amount, '
                    'which is not allowed.\n\n'
                    'Please change this tax to one with a zero amount in the "Sales Orders" tab of '
                    'the integration settings.'
                ) % integration.name

            if error:
                raise UserError(error)
        elif policy == 'take_from_product':
            taxes = product.taxes_id.filtered(lambda x: x.company_id == integration.company_id)

        return taxes

    def try_get_odoo_tax(self, tax_id):
        integration = self.integration_id
        tax = self.env['account.tax'].from_external(
            integration,
            tax_id,
            raise_error=False,
        )

        if tax:
            return tax

        tax = integration._import_external_tax(tax_id)

        if not tax:
            raise NotMappedFromExternal(
                _(
                    'Failed to find the external tax with code "%s".\n\n'
                    'To resolve this issue, please run "Import Master Data" by clicking the button on '
                    'the "Initial Import" tab in your "%s" integration settings.\n'
                    'After that, verify that all taxes are correctly mapped in the "Mappings → Taxes" menu.'
                ) % (tax_id, integration.name),
                model_name='integration.account.tax.external',
                code=tax_id,
                integration=integration,
            )

        return tax

    def _get_tax_price_included(self, taxes):
        price_include = all(tax.price_include for tax in taxes)

        if not price_include and any(tax.price_include for tax in taxes):
            raise ApiImportError(
                _(
                    'There is a mismatch in the "Included in Price" parameter across the taxes applied '
                    'to a line item.\n\n'
                    'Some taxes are marked as "Included in Price" while others are not, which is not allowed.\n\n'
                    'To resolve this issue, please ensure that all taxes applied to the item either include or exclude '
                    'the price consistently.'
                )
            )

        # If True - the price includes taxes
        return price_include

    def try_get_odoo_delivery_carrier(self, carrier_data):
        integration = self.integration_id
        code = carrier_data['id']
        carrier = self.env['delivery.carrier'].from_external(
            integration,
            code,
            raise_error=False,
        )
        if carrier:
            return carrier

        carrier = integration._import_external_carrier(carrier_data)

        if not carrier:
            raise NotMappedFromExternal(
                _(
                    'Failed to find the external delivery carrier with code "%s".\n\n'
                    'To resolve this issue, please run "Import Master Data" by clicking the button on '
                    'the "Initial Import" tab in your "%s" integration settings.\n'
                    'After that, verify that all delivery carriers are correctly mapped in '
                    'the "Mappings → Shipping Methods" menu.'
                ) % (code, integration.name),
                model_name='integration.delivery.carrier.external',
                code=code,
                integration=integration,
            )

        return carrier

    def _create_delivery_line(self, order, delivery_data):
        carrier = delivery_data['carrier'] or dict()
        if not carrier.get('id'):
            return self.env['sale.order.line']

        # 1. Set delivery line
        integration = self.integration_id
        carrier = self.try_get_odoo_delivery_carrier(carrier)
        order.set_delivery_line(carrier, delivery_data['shipping_cost'])

        delivery_line = order.order_line.filtered(lambda line: line.is_delivery)
        if not delivery_line:
            return delivery_line

        # 2. Apply taxes
        delivery_product = delivery_line.product_id
        taxes = self.get_taxes_from_external_list(
            delivery_product,
            delivery_data.get('taxes', []),
        )

        tax_ids = taxes.ids
        if taxes and delivery_data.get('carrier_tax_rate') == 0:
            if not all(x.amount == 0 for x in taxes):
                tax_ids = list()

        delivery_line.tax_ids = [(6, 0, tax_ids)]

        # 3. Handle `tax-exclude` property
        if 'shipping_cost_tax_excl' in delivery_data:
            if not delivery_line.tax_ids or not self._get_tax_price_included(delivery_line.tax_ids):
                delivery_line.price_unit = delivery_data['shipping_cost_tax_excl']

        # 4. Apply discount
        if delivery_data.get('discount'):
            if integration.separate_discount_line:
                discount_line_vals = self._prepare_order_discount_line_vals(
                    order,
                    delivery_data,
                    product=delivery_product,
                )
                if discount_line_vals:
                    order.order_line = [(0, 0, discount_line_vals)]
            else:
                delivery_line.discount = delivery_data['discount']['discount_percent']

        # 5. Update notes
        if integration.so_delivery_note_field and delivery_data.get('delivery_notes'):
            setattr(
                order,
                integration.so_delivery_note_field.name,
                delivery_data['delivery_notes'],
            )

        return delivery_line

    def _create_gift_line(self, order, gift_data):
        if not gift_data.get('do_gift_wrapping'):
            return self.env['sale.order.line']

        integration = self.integration_id
        product = integration.gift_wrapping_product_id
        if not product:
            raise ApiImportError(
                _(
                    'The "Gift Wrapping Product" is not configured for the "%s" integration.\n\n'
                    'To resolve this issue, please configure the "Gift Wrapping Product" in '
                    'the "Sales Orders" tab of the integration settings.'
                ) % integration.name
            )

        taxes = self.get_taxes_from_external_list(
            product,
            gift_data.get('wrapping_tax_ids', []),
        )

        if self._get_tax_price_included(taxes):
            gift_price = gift_data.get('total_wrapping_tax_incl', 0)
        else:
            gift_price = gift_data.get('total_wrapping_tax_excl', 0)

        line = self.env['sale.order.line'].create({
            'product_id': product.id,
            'order_id': order.id,
            'tax_ids': taxes.ids,
            'price_unit': gift_price,
        })

        message = gift_data.get('gift_message')
        if message:
            line._process_gift_message(message)

        return line

    def _create_line_with_price_difference_product(self, order, amount_total):
        integration = self.integration_id

        price_difference = float_round(
            value=amount_total - order.amount_total,
            precision_digits=self.env['decimal.precision'].precision_get('Product Price'),
        )

        if price_difference:
            if price_difference > 0:
                difference_product_id = integration.positive_price_difference_product_id
            else:
                difference_product_id = integration.negative_price_difference_product_id

            if not difference_product_id:
                raise ApiImportError(
                    _(
                        'The total amount in the sales order from "%s" differs from '
                        'the calculated amount in Odoo, usually due to rounding issues or tax discrepancies.\n'
                        'Order amounts: %f (Odoo) vs %f (%s)\n\n'
                        'Odoo and "%s" calculate taxes differently, which can lead to this issue. '
                        'To resolve it, you can either:\n'
                        '1. Go to "E-Commerce Integrations → Stores → %s".\n'
                        'Navigate to the "Sales Orders" tab, and in the "Order Extras Management" section, '
                        'configure the products to be used for compensating price differences.\n'
                        '2. Alternatively, you can disable the "Order Total Difference Correction" checkbox on '
                        'the same tab if you do not want Odoo to handle price discrepancies.\n\n'
                        'Once the issue is resolved, requeue the job, and the sales order will '
                        'be created in Odoo with the correct total.'
                    ) % (
                        integration.name,
                        order.amount_total,
                        amount_total,
                        integration.name,
                        integration.name,
                        integration.name
                    )
                )

            return self.env['sale.order.line'].create({
                'product_id': difference_product_id.id,
                'order_id': order.id,
                'price_unit': price_difference,
                'tax_ids': False,
            })

        return False

    def _insert_line_in_order(self, order, price_unit, tax_ids):
        discount_product = self.integration_id.discount_product_id

        line = self.env['sale.order.line'].create({
            'product_id': discount_product.id,
            'order_id': order.id,
            'price_unit': price_unit,
            'tax_ids': tax_ids and tax_ids.ids or False,
        })
        return line

    def _create_discount_line(self, order, discount_data):
        discount_tax_incl = discount_data.get('total_discounts_tax_incl')
        discount_tax_excl = discount_data.get('total_discounts_tax_excl')
        if not discount_tax_incl or not discount_tax_excl:
            return self.env['sale.order.line']

        discount_tax_incl = abs(discount_tax_incl)
        discount_tax_excl = abs(discount_tax_excl)

        integration = self.integration_id
        if not integration.discount_product_id:
            raise ApiImportError(
                _(
                    'Discount Product is not configured for the "%s" integration.\n'
                    'To resolve this issue, please configure the "Discount Product" setting in '
                    'the "Sales Orders" tab of the integration settings:\n'
                    '1. Go to "E-Commerce Integrations -> %s -> Sales Orders" tab.\n'
                    '2. Set the "Discount Product" field.\n\n'
                    'Once this is done, requeue the job to continue processing.'
                ) % (integration.name, integration.name)
            )

        precision = self.env['decimal.precision'].precision_get('Product Price')

        product_lines = order.order_line.filtered(lambda x: not x.is_delivery)

        # Taxes must be with '-'
        discount_taxes = discount_tax_excl - discount_tax_incl

        if self._get_tax_price_included(product_lines.mapped('tax_ids')):
            discount_price = discount_tax_incl * -1
        else:
            discount_price = discount_tax_excl * -1

        discount_line = self._insert_line_in_order(order, discount_price, False)

        # 1. Discount without taxes
        if float_is_zero(discount_taxes, precision_digits=precision):
            return discount_line

        # 2. Try to find the most suitable tax.
        #  Basically it's made for PrestaShop because it gives only discount with/without taxes
        #  We try to understand whether discount applied to all lines, one line
        #  or lines with identical taxes by the minimal calculated tax difference.
        #  Otherwise we apply discount to all lines
        #  TODO For Other shops we should make with taxes from discount in order data

        # 2.1 Group lines by taxes
        all_grouped_taxes = {}
        grouped_taxes = {}
        line_taxes = {}
        all_lines_sum = 0
        delivery_line = order.order_line.filtered(lambda line: line.is_delivery)
        carrier_tax_id = delivery_line.tax_ids

        for line in product_lines:
            tax_key = str(line.tax_ids)
            line_key = str(line.id)
            all_lines_sum += line.price_subtotal

            grouped_taxes.update({tax_key: {
                'tax_ids': line.tax_ids if line.price_unit and not all_lines_sum else carrier_tax_id,
                'discount': discount_price,
            }})
            line_taxes.update({line_key: {
                'tax_ids': line.tax_ids,
                'discount': discount_price,
            }})
            all_grouped_taxes.update({tax_key: {
                'price_subtotal': (
                    line.price_subtotal
                    + all_grouped_taxes.get(tax_key, {}).get('price_subtotal', 0)
                ),
                'tax_ids': line.tax_ids,
            }})

        # 2.2 Distribution of the amount to different tax groups
        all_grouped_taxes = [grouped_tax for grouped_tax in all_grouped_taxes.values()]
        residual_amount = discount_price
        line_num = len(all_grouped_taxes)

        for tax_value in all_grouped_taxes:
            if line_num == 1 or not all_lines_sum:
                tax_value['discount'] = residual_amount
            else:
                tax_value['discount'] = float_round(
                    value=discount_price * tax_value['price_subtotal'] / all_lines_sum,
                    precision_digits=precision
                )

            residual_amount -= tax_value['discount']
            line_num -= 1

        # 2.3 Calculate tax difference for different combinations
        def calc_tax_summa(tax_values):
            tax_amount = 0

            for tax_value in tax_values:
                discount_line.tax_ids = tax_value['tax_ids']
                discount_line.price_unit = tax_value['discount']
                tax_amount += discount_line.price_tax

            return {
                'grouped_taxes': tax_values,
                'tax_diff': abs(tax_amount - discount_taxes),
            }

        # discount taxes for all
        calc_taxes = [calc_tax_summa(all_grouped_taxes)]
        # discount taxes one by one for tax groups
        calc_taxes += [calc_tax_summa([grouped_tax]) for grouped_tax in grouped_taxes.values()]
        # discount taxes one by one for line
        calc_taxes += [calc_tax_summa([line_tax]) for line_tax in line_taxes.values()]

        # 2.4 Get tax with MINIMAL difference
        # If price difference > 1% then apply discount to all taxes
        calc_taxes.sort(key=lambda calc_tax: calc_tax['tax_diff'])

        if abs(calc_taxes[0]['tax_diff'] / discount_taxes) < 0.01:
            the_most_suitable_discount = calc_taxes[0]['grouped_taxes']
        else:
            the_most_suitable_discount = all_grouped_taxes

        # Delete old delivery line
        discount_line.unlink()

        discount_lines = self.env['sale.order.line']

        # 2.5 Create discount lines for discount
        for tax_value in the_most_suitable_discount:
            discount_lines += self._insert_line_in_order(
                order,
                tax_value['discount'],
                tax_value['tax_ids']
            )

        return discount_lines

    def _get_payment_method(self, external_code):
        integration = self.integration_id
        _name = 'sale.order.payment.method'
        PaymentMethod = self.env[_name]

        payment_method = PaymentMethod.from_external(
            integration,
            external_code,
            raise_error=False,
        )

        if not payment_method:
            payment_method = PaymentMethod.search([
                ('name', '=', external_code),
                ('integration_id', '=', integration.id),
            ])

            if not payment_method:
                payment_method = PaymentMethod.create({
                    'name': external_code,
                    'integration_id': integration.id,
                })

            self.env[f'integration.{_name}.mapping'].create_integration_mapping(
                integration,
                payment_method,
                external_code,
                dict(name=external_code),
            )

        return payment_method

    def _post_create_order(self, order: models.Model, order_data: Dict):
        return order

    def _get_translated_string(self, source: str, *args, lang: str = None) -> str:
        """
        Get a translated string in the specified language.

        :param lang: Language code (e.g., 'pl_PL', 'en_US')
        :param source: string to be translated
        :param args: Arguments for string formatting
        :return: Translated and formatted string
        """
        if not source:
            return ''

        # Prepare a `context` local variable so Odoo's GettextAlias (_()) can detect `lang`
        # by inspecting the caller's locals and translate `source` in that language
        context = dict(self.env.context, lang=lang) if lang else self.env.context  # noqa: F841

        # Translate using Odoo's global alias; language is taken from the local `context` above
        translated = _(source)

        if not args:
            return translated

        translated = translated % args

        return translated
