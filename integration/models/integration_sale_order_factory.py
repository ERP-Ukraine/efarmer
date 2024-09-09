# See LICENSE file for full copyright and licensing details.

import logging
import warnings
from typing import Dict

from odoo import models, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_is_zero, float_round

from ..exceptions import ApiImportError, NotMappedFromExternal


_logger = logging.getLogger(__name__)


class IntegrationSaleOrderFactory(models.AbstractModel):
    _name = 'integration.sale.order.factory'
    _description = 'Integration Sale Order Factory'

    @api.model
    def create_order(self, integration, order_data):
        order = self.env['integration.sale.order.mapping'].search([
            ('integration_id', '=', integration.id),
            ('external_id.code', '=', order_data['id']),
        ]).odoo_id
        if not order:
            order = self._create_order(integration, order_data)
            order.create_mapping(integration, order_data['id'], extra_vals={'name': order.name})
            self._post_create_order(integration, order, order_data)
        return order

    @api.model
    def _create_order(self, integration, order_data):
        order_vals = self._prepare_order_vals(integration, order_data)

        order_name = self.env['sale.order']\
            .get_integration_order_name(integration, order_data['ref'])

        if order_name:
            order_vals['name'] = order_name

        order = self.env['sale.order'].create(order_vals)
        order.onchange_partner_id()
        # Additional Order adjustments
        order._apply_values_from_external(order_data)

        # Configure dictionary with the default/force values after `onchange_partner_id()` method
        values = {
            'partner_invoice_id': order_vals['partner_invoice_id'],
            'partner_shipping_id': order_vals['partner_shipping_id'],
        }

        if order_vals['pricelist_id']:
            values['pricelist_id'] = order_vals['pricelist_id']

        if integration.default_sales_team_id:
            values['team_id'] = integration.default_sales_team_id.id

        if integration.default_sales_person_id:
            values['user_id'] = integration.default_sales_person_id.id

        fiscal_position = self.env['account.fiscal.position'].with_company(order.company_id)\
            .get_fiscal_position(order.partner_id.id, order_vals['partner_shipping_id'])
        values['fiscal_position_id'] = fiscal_position.id

        # Payment Terms should be set after order is created because after order is created
        # onchange/depends functions are called. And they are changing payment terms
        # and as result they are taken from res.partner. And we have functionality to force set
        # Payment Terms from the payment method
        payment_method = self._get_payment_method(
            integration,
            order_data['payment_method'],
        )
        values['payment_method_id'] = payment_method.id
        payment_method_external = payment_method.to_external_record(integration)
        if payment_method_external.payment_term_id:
            values['payment_term_id'] = payment_method_external.payment_term_id.id

        order.write(values)

        self._create_order_additional_lines(order, order_data)

        # Recompute taxes based on the fiscal position
        # if order.fiscal_position_id:
        #     order._compute_tax_id()

        return order

    def _create_order_additional_lines(self, order, order_data):
        # 1. Creating Delivery Line
        self._create_delivery_line(order, order_data['delivery_data'])

        # 2. Creating Discount Line.
        # !!! It should be after Creating Delivery Line
        self._create_discount_line(order, order_data['discount_data'])  # Prestashop only

        # 3. Creating Gift Wrapping Line
        self._create_gift_line(order, order_data['gift_data'])

        # 4. Check difference of total order amount and correct it
        #    !!! This block must be the last !!!
        if order.integration_id.use_order_total_difference_correction:
            if order_data.get('amount_total', False):
                self._create_line_with_price_difference_product(order, order_data['amount_total'])

        self._add_payment_transactions(
            order,
            order_data.get('payment_transactions'),
        )

    @api.model
    def _prepare_order_vals_hook(self, integration, original_order_data, create_order_vals):
        # Use this method to override in subclasses to define different behavior
        # of preparation of order values
        pass

    @api.model
    def _prepare_order_vals(self, integration, order_data):
        """
        Prepare order values for creating a sale order.
        Args:
            integration: Sale integration record.
            order_data: Dictionary containing order data.
        Returns:
            dict: Prepared order values.
        """
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

        lines_to_create = []
        for line in order_data['lines']:
            line_vals = self._prepare_order_line_vals(integration, line)
            lines_to_create.append((0, 0, line_vals))

            # Create separate discount line
            if integration.separate_discount_line:
                discount_line_vals = self._prepare_order_discount_line_vals(integration, line)
                if discount_line_vals:
                    lines_to_create.append((0, 0, discount_line_vals))

        order_vals = {
            'integration_id': integration.id,
            'integration_amount_total': order_data.get('amount_total', False),
            'partner_id': partner.id if partner else False,
            'partner_shipping_id': shipping.id if shipping else False,
            'partner_invoice_id': billing.id if billing else False,
            'order_line': lines_to_create,
        }

        if integration.so_external_reference_field:
            order_vals[integration.so_external_reference_field.name] = order_data['ref']

        if order_data.get('date_order'):
            external_date_converted = integration._set_zero_time_zone(order_data['date_order'])
            order_vals['date_order'] = external_date_converted

        current_state = order_data.get('current_order_state')
        if current_state:
            sub_status = self._get_order_sub_status(
                integration,
                current_state,
            )
            order_vals['sub_status_id'] = sub_status.id

        pricelist = self._get_order_pricelist(integration, order_data)
        if pricelist:
            order_vals['pricelist_id'] = pricelist.id

        self._prepare_order_vals_hook(integration, order_data, order_vals)

        return order_vals

    @api.model
    def _prepare_order_discount_line_vals(self, integration, line_data, odoo_product=None):
        discount = line_data['discount']
        assert isinstance(discount, dict), _('Expected the dict object')

        if not discount or not discount.get('discount_amount'):
            return dict()

        discount_product = integration.discount_product_id
        if not discount_product:
            raise ApiImportError(_('Discount Product is empty. Please, fill it in '
                                   'Sale Integration on the tab "Sale Order Defaults"'))

        if not odoo_product:
            odoo_product = self._try_get_odoo_product(integration, line_data)

        discount_price = discount['discount_amount']
        taxes = self.get_taxes_from_external_list(odoo_product, integration, line_data['taxes'])

        if discount.get('discount_amount_tax_incl'):
            if taxes and self._get_tax_price_included(taxes):
                discount_price = discount['discount_amount_tax_incl']

        # Negate the discount price to ensure it's represented as a negative value.
        # This is necessary because discounts are typically negative values in accounting.
        discount_price = discount_price * -1

        # create discount line values dictionary
        return {
            'product_id': discount_product.id,
            'name': 'Discount for ' + odoo_product.display_name,
            'price_unit': discount_price,
            'product_uom_qty': 1,
            'tax_id': [(6, 0, taxes.ids)],
        }

    @api.model
    def _get_order_sub_status(self, integration, ext_current_state):
        SubStatus = self.env['sale.order.sub.status']

        sub_status = SubStatus.from_external(
            integration, ext_current_state, raise_error=False)

        if not sub_status:
            integration.integrationApiImportSaleOrderStatuses()
            sub_status = SubStatus.from_external(integration, ext_current_state)

        return sub_status

    def _get_order_pricelist(self, integration, order_data):
        company = integration.company_id
        company_currency_iso = company.currency_id.name
        ecommerce_currency_iso = order_data.get('currency', '')

        if not all([company_currency_iso, ecommerce_currency_iso]):
            return False

        if company_currency_iso.lower() == ecommerce_currency_iso.lower():
            return False

        odoo_currency = self.env['res.currency'].search([
            ('name', '=ilike', ecommerce_currency_iso.lower()),
        ], limit=1)
        if not odoo_currency:
            raise ApiImportError(_(
                'Currency ISO code "%s" was not found in Odoo.' % ecommerce_currency_iso
            ))

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
                'name': f'Integration {ecommerce_currency_iso}',
            }
            pricelist = Pricelist.create(vals)

        return pricelist

    @api.model
    def _get_odoo_product(self, integration, variant_code, raise_error=False):
        product = self.env['product.product'].from_external(
            integration,
            variant_code,
            raise_error=False,
        )

        if not product and raise_error:
            raise NotMappedFromExternal(_(
                'Failed to find external variant with code "%s". Please, run "IMPORT PRODUCT '
                'FROM EXTERNAL" using button on "Initial Import" tab on your sales integration '
                'with name "%s". After this make sure that all your products are mapped '
                'in "Mappings - Products" and "Mappings - '
                'Variants" menus.') % (variant_code, integration.name),
                'integration.product.product.external', variant_code, integration,
            )

        return product

    @api.model
    def _try_get_odoo_product(self, integration, line, force_create=False):
        complex_variant_code = line['product_id']

        product = self._get_odoo_product(integration, complex_variant_code)
        if product:
            return product

        # If the product is not found, attempt to re-import it from the external system
        template_code, __ = integration.adapter._parse_product_external_code(complex_variant_code)
        external_template, external_variants, errors = integration._import_external_product(template_code)

        # Use fallback product if no external templates found or variant code doesn't match.
        if not external_template or complex_variant_code not in external_variants.mapped('code'):
            if integration.fallback_product_id:
                return integration.fallback_product_id

            raise ValidationError(_(
                'Order contains a line item missing product details (empty product ID or SKU), '
                'often resulting from removed products or custom items added via order editing. '
                'Product information is essential for order import. Resolve this by configuring '
                'the Fallback Product in the integration settings (Sales Orders tab), '
                'or alternatively, adjust the order manually to correct the issue.'
            ))

        auto_create_product = force_create or integration.auto_create_products_on_so
        product = self._get_odoo_product(
            integration,
            complex_variant_code,
            raise_error=(not auto_create_product),
        )

        if auto_create_product and not product:
            # Try to create ERP product on the fly
            external_record = self.env['integration.product.template.external']\
                .get_external_by_code(integration, template_code)

            integration.import_product(external_record.id, import_images=True)
            product = self._get_odoo_product(integration, complex_variant_code, raise_error=True)

        return product

    @api.model
    def _prepare_order_line_vals(self, integration, line):
        """
        Set forcibly discount to zero to avoid affection of the price list
        with policy "Show public price & discount to the customer".
        If necessary, the discount will be created as a sepatare line.
        """
        product = self._try_get_odoo_product(integration, line)
        vals = {
            'discount': 0,
            'product_id': product.id,
            'integration_external_id': line['id'],
            'external_location_id': line.get('external_location_id', False),
        }

        if 'product_uom_qty' in line:
            vals['product_uom_qty'] = line['product_uom_qty']

        taxes = self.get_taxes_from_external_list(product, integration, line['taxes'])
        vals['tax_id'] = [(6, 0, taxes.ids)]

        vals['price_unit'] = line['price_unit']
        if taxes and self._get_tax_price_included(taxes):
            if line.get('price_unit_tax_incl'):
                vals['price_unit'] = line['price_unit_tax_incl']

        if line.get('add_description_list'):
            data_list = line['add_description_list']
            vals['name'] = self._update_order_description(product, data_list)

        # Create discount included in the line
        if not integration.separate_discount_line and line.get('discount'):
            vals['discount'] = line['discount']['discount_percent']

        return vals

    def _update_order_description(self, product, data_list):
        description = product.get_product_multiline_description_sale()
        return description + '\n' + '\n'.join(data_list)

    def get_taxes_from_external_list(self, product, integration, external_tax_ids):
        taxes = self.env['account.tax']

        if external_tax_ids:
            for external_tax_id in external_tax_ids:
                taxes |= self.try_get_odoo_tax(integration, external_tax_id)
            return taxes

        policy = integration.behavior_on_empty_tax

        if policy == 'leave_empty':
            pass
        elif policy == 'set_special_tax':
            error = None
            taxes = integration.zero_tax_id

            if not taxes:
                error = _(
                    '"Special Zero Tax" not specified for the "%s" integration '
                    'on "Sale Order Defaults" tab.' % integration.name
                )
            elif taxes.amount:
                error = _(
                    'Non zero amount not allowed for "Special Zero Tax". Change it '
                    'for the "%s" integration on "Sale Order Defaults" tab.' % integration.name
                )
            if error:
                raise UserError(error)
        elif policy == 'take_from_product':
            taxes = product.taxes_id

        return taxes

    def try_get_odoo_tax(self, integration, tax_id):
        tax = self.env['account.tax'].from_external(
            integration,
            tax_id,
            raise_error=False,
        )

        if tax:
            return tax

        tax = integration._import_external_tax(tax_id)

        if not tax:
            raise NotMappedFromExternal(_(
                'Failed to find external tax with code "%s". Please, run "IMPORT MASTER DATA" '
                'using button on "Initial Import" tab on your sales integration "%s". '
                'After this make sure that all your delivery carrier are mapped '
                'in "Mappings - Taxes" menus.') % (tax_id, integration.name),
                'integration.account.tax.external', tax_id, integration,
            )

        return tax

    @api.model
    def _get_tax_price_included(self, taxes):
        price_include = all(tax.price_include for tax in taxes)

        if not price_include and any(tax.price_include for tax in taxes):
            raise ApiImportError(_('One line has different Included In Price parameter in Taxes'))

        # If True - the price includes taxes
        return price_include

    def try_get_odoo_delivery_carrier(self, integration, carrier_data):
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
            raise NotMappedFromExternal(_(
                'Failed to find external carrier with code "%s". Please, run "IMPORT MASTER DATA" '
                'using button on "Initial Import" tab on your sales integration "%s". '
                'After this make sure that all your delivery carrier are mapped '
                'in "Mappings - Shipping Methods" menus.') % (code, integration.name),
                'integration.delivery.carrier.external', code, integration,
            )

        return carrier

    def _create_delivery_line(self, order, delivery_data):
        carrier = delivery_data['carrier'] or dict()
        if not carrier.get('id'):
            return self.env['sale.order.line']

        # 1. Set delivery line
        integration = order.integration_id
        carrier = self.try_get_odoo_delivery_carrier(integration, carrier)
        order.set_delivery_line(carrier, delivery_data['shipping_cost'])

        delivery_line = order.order_line.filtered(lambda line: line.is_delivery)
        if not delivery_line:
            return delivery_line

        # 2. Apply taxes
        taxes = self.get_taxes_from_external_list(
            delivery_line.product_id,
            integration,
            delivery_data.get('taxes', []),
        )

        tax_ids = taxes.ids
        if taxes and delivery_data.get('carrier_tax_rate') == 0:
            if not all(x.amount == 0 for x in taxes):
                tax_ids = list()

        delivery_line.tax_id = [(6, 0, tax_ids)]

        # 3. Handle `tax-exclude` property
        if 'shipping_cost_tax_excl' in delivery_data:
            if not self._get_tax_price_included(delivery_line.tax_id):
                delivery_line.price_unit = delivery_data['shipping_cost_tax_excl']

        # 4. Apply discount
        if delivery_data.get('discount'):
            if integration.separate_discount_line:
                discount_line_vals = self._prepare_order_discount_line_vals(
                    integration,
                    delivery_data,
                    odoo_product=delivery_line.product_id,
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

        integration = order.integration_id
        product = integration.gift_wrapping_product_id
        if not product:
            raise ApiImportError(_(
                'Gift Wrapping Product is empty. Please, fill it in '
                'Sale Integration on the tab "Sale Order Defaults".'
            ))

        taxes = self.get_taxes_from_external_list(
            product,
            integration,
            gift_data.get('wrapping_tax_ids', []),
        )

        if self._get_tax_price_included(taxes):
            gift_price = gift_data.get('total_wrapping_tax_incl', 0)
        else:
            gift_price = gift_data.get('total_wrapping_tax_excl', 0)

        line = self.env['sale.order.line'].create({
            'product_id': product.id,
            'order_id': order.id,
            'tax_id': taxes.ids,
            'price_unit': gift_price,
        })

        message = gift_data.get('gift_message')
        if message:
            line._process_gift_message(message)

        return line

    def _create_line_with_price_difference_product(self, order, amount_total):
        integration = order.integration_id

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
                    _('Total amount in sales order from {type_api} is not the same as calculated '
                      'amount in Odoo. That usually happens because of rounding issues. Odoo '
                      'and {type_api} calculate taxes differently. To import an order you need '
                      'to go to the menu “e-Commerce Integrations → Integration → select your '
                      'Integration“. Go to the tab “Sales Order Defaults“ and in the “Pricing '
                      'Calculation“ section select products that will be used for order lines '
                      'that will be automatically added to sales orders in Odoo to compensate '
                      'for this difference. So the total amount will be similar between '
                      '{type_api} and Odoo. After this, you can “Requeue“ job and Sales Order '
                      'will be created in Odoo.').format(type_api=integration.type_api))

            difference_line = self.env['sale.order.line'].create({
                'product_id': difference_product_id.id,
                'order_id': order.id,
            })

            difference_line.product_id_change()
            difference_line.price_unit = price_difference
            difference_line.tax_id = False

            return difference_line

        return False

    def _insert_line_in_order(self, order, price_unit, tax_id):
        discount_product = order.integration_id.discount_product_id

        line = self.env['sale.order.line'].create({
            'name': discount_product.name,
            'product_id': discount_product.id,
            'order_id': order.id,
        })
        # This method fills name and other product info
        line.product_id_change()

        line.update({
            'price_unit': price_unit,
            'tax_id': tax_id and tax_id.ids or False,
        })
        return line

    def _create_discount_line(self, order, discount_data):
        discount_tax_incl = discount_data.get('total_discounts_tax_incl')
        discount_tax_excl = discount_data.get('total_discounts_tax_excl')
        if not discount_tax_incl or not discount_tax_excl:
            return self.env['sale.order.line']

        discount_tax_incl = abs(discount_tax_incl)
        discount_tax_excl = abs(discount_tax_excl)

        integration = order.integration_id
        if not integration.discount_product_id:
            raise ApiImportError(_('Discount Product is empty. Please, fill it in '
                                   'Sale Integration on the tab "Sale Order Defaults"'))

        precision = self.env['decimal.precision'].precision_get('Product Price')

        product_lines = order.order_line.filtered(lambda x: not x.is_delivery)

        # Taxes must be with '-'
        discount_taxes = discount_tax_excl - discount_tax_incl

        if self._get_tax_price_included(product_lines.mapped('tax_id')):
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
        carrier_tax_id = delivery_line.tax_id

        for line in product_lines:
            tax_key = str(line.tax_id)
            line_key = str(line.id)
            all_lines_sum += line.price_subtotal

            grouped_taxes.update({tax_key: {
                'tax_id': line.tax_id if line.price_unit and not all_lines_sum else carrier_tax_id,
                'discount': discount_price,
            }})
            line_taxes.update({line_key: {
                'tax_id': line.tax_id,
                'discount': discount_price,
            }})
            all_grouped_taxes.update({tax_key: {
                'price_subtotal': (
                    line.price_subtotal
                    + all_grouped_taxes.get(tax_key, {}).get('price_subtotal', 0)
                ),
                'tax_id': line.tax_id,
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
                discount_line.tax_id = tax_value['tax_id']
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
                tax_value['tax_id']
            )

        return discount_lines

    def _add_payment_transactions(self, order, payment_transactions):
        if not payment_transactions:
            return

        # TODO: Integrate payment functionality in the integration module
        # TODO: Handle 'order_transactions' key and '_apply_values_from_external'
        if 'account_payment_ids' not in self.env['sale.order']._fields:
            return

        integration = order.integration_id
        precision = self.env['decimal.precision'].precision_get('Product Price')
        for transaction in payment_transactions:
            # we skip zero transaction as they doesn't make sense
            if float_is_zero(transaction['amount'], precision_digits=precision):
                _logger.warning(_('Order % was received with payment amount equal to 0.0. '
                                  'Skipping payment attachment to the order') % order.name)
                continue
            if not transaction['transaction_id']:
                _logger.warning(_('Order % payment doesn\'t have transaction id specified.'
                                  ' Skipping payment attachment to the order') % order.name)
                continue

            # Currency is not required field for transaction,
            # so we calculate it either from pricelist
            # or from company related to SO
            # And then try to get it from received SO
            currency_id = order.pricelist_id.currency_id.id or order.company_id.currency_id.id
            if transaction.get('currency'):
                odoo_currency = self.env['res.currency'].search([
                    ('name', '=ilike', transaction['currency'].lower()),
                ], limit=1)
                if not odoo_currency:
                    raise ApiImportError(
                        _('Currency ISO code "%s" was not found in Odoo.') % transaction['currency']
                    )
                currency_id = odoo_currency.id

            # Get Payment journal based on the payment method
            external_payment_method = order.payment_method_id.to_external_record(integration)

            if not external_payment_method.payment_journal_id:
                raise UserError(
                    _('No Payment Journal defined for Payment Method "%s". '
                      'Please, define it in menu "e-Commerce Integration -> Auto-Workflow -> '
                      'Payment Methods" in the "Payment Journal" column')
                    % order.payment_method_id.name
                )
            payment_vals = {
                'date': transaction['transaction_date'],
                'amount': abs(transaction['amount']),  # can be negative, so taking absolute value
                'payment_type': 'inbound' if transaction['amount'] > 0.0 else 'outbound',
                'partner_type': 'customer',
                'ref': transaction['transaction_id'],
                'journal_id': external_payment_method.payment_journal_id.id,
                'currency_id': currency_id,
                'partner_id': order.partner_invoice_id.commercial_partner_id.id,
                'payment_method_id': self.env.ref(
                    'account.account_payment_method_manual_in'  # TODO: set smth else
                ).id,
            }

            payment_obj = self.env['account.payment']
            payment = payment_obj.create(payment_vals)
            order.account_payment_ids |= payment
            payment.action_post()

            Transaction = self.env['external.order.transaction']\
                .with_context(integration_id=integration.id)
            txn_id = Transaction._get_or_create_txn_from_external(transaction)
            order.external_payment_ids = [(4, txn_id.id, 0)]

    @api.model
    def _get_payment_method(self, integration, external_code):
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

    def _post_create_order(self, integration: models.Model, order: models.Model, order_data: Dict):
        if hasattr(self, '_post_create'):
            warnings.warn('Deprecated method used: _post_create', DeprecationWarning, stacklevel=2)
            self._post_create(integration, order)
        return order
