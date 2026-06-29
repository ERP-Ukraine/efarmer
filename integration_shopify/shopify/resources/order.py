# See LICENSE file for full copyright and licensing details.

from types import SimpleNamespace

from .base import ShopifyResourceUpdate
from .metafields_mixin import MetafieldMixin


class OrderParseMixin:

    def __init__(self, *args, **kwargs):
        self._props = SimpleNamespace(
            use_customer_currency=False,
            personal_id_additional_field_name='',
            vat_number_additional_field_name='',
        )
        self._order_line_items = []

    @property
    def props(self):
        return self._props

    @property
    def order_line_items(self):
        self.ensure_one()

        if not self._order_line_items:
            for data in (self['lineItems'] or []):
                line = self._env.OrderLineItem.set(**data)
                line._order = self

                self._order_line_items.append(line)

        return self._order_line_items

    def update_props(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self.props, key, value)

    def parse(self, **kwargs):
        self.ensure_one()

        # 0. Update props
        self.update_props(**kwargs)

        # 1. Parse order values
        lines = self.parse_lines()
        payment_method = self.parse_payment_method()
        payment_methods = self.parse_payment_gateway_names()
        amount_total = self.parse_price_total()
        delivery_data = self.parse_delivery_data()
        order_risks = self.parse_order_risks()
        payment_transactions = self.parse_payment_transactions()
        integration_workflow_states = self.parse_workflow_states()
        currency_code = self.parse_currency_code()
        order_fulfillments = self.parse_fulfillments()
        sale_channel_data = self.parse_sale_channel()
        customer_data = self.parse_customer_data()

        return {
            'id': self.id_str,
            'ref': self.name,
            'date_order': self.created_at,
            'lines': lines,
            'payment_method': payment_method,
            'payment_methods': payment_methods,
            'amount_total': amount_total,
            'delivery_data': delivery_data,
            'discount_data': {},  # Prestashop only
            'gift_data': {},
            'order_risks': order_risks,
            'payment_transactions': payment_transactions,
            'current_order_state': '',
            'external_tags': self.tags,
            'is_cancelled': self.is_cancelled,
            'external_location_id': self.location_id,
            'integration_workflow_states': integration_workflow_states,
            'currency': currency_code,
            'order_fulfillments': order_fulfillments,
            'sale_channel_data': sale_channel_data,
            'order_source_name': self.source_name,
            'custom_attributes': self.custom_attributes,
            **customer_data,
        }

    def parse_lines(self):
        self.ensure_one()

        # 1. Reset the quantity to the original value
        for line in self.order_line_items:
            line.drop_key('current_quantity_tmp')

        # 2. Group lines by location
        lines_by_location = self._group_lines_by_location()

        # 3. Parse line accouring to location requested quantity
        result = []
        for location_id, items in lines_by_location:
            for (order_line_id, fulfillment_order_qty) in items:
                order_line = self._get_order_line_by_id(order_line_id)

                available_qty = order_line.current_quantity_tmp
                if available_qty <= 0:
                    continue

                fulfillment_order_qty = order_line.current_quantity_tmp
                requested_qty = fulfillment_order_qty if (available_qty >= fulfillment_order_qty) else available_qty
                order_line.set(current_quantity_tmp=available_qty - requested_qty)

                data = order_line.parse(requested_qty)
                data['external_location_id'] = location_id

                result.append(data)

        return result

    def parse_payment_gateway_names(self) -> list:
        self.ensure_one()

        names = self.payment_gateway_names
        OrderTransaction = self._env.OrderTransaction.cls

        if not names:
            return [OrderTransaction.format_payment_code(False)]
        return [OrderTransaction.format_payment_code(x) for x in names]

    def parse_payment_method(self):
        return self.parse_payment_gateway_names()[-1]

    def parse_price_total(self):
        money_bag = self.current_total_price_set
        return money_bag.get_amount(self.props.use_customer_currency)

    def parse_delivery_data(self):
        """
        Resolve the delivery carrier and shipping cost for the order.

        The carrier is taken from the fulfillment order's delivery method when it is
        valid. For marketplace orders (e.g. Amazon via Marketplace Connect) the
        delivery method carries no service code (so `delivery_method.is_valid` is
        False), while the carrier identity lives on the order's shipping line. In that
        case we fall back to the shipping line via `_carrier_from_shipping_line`, which
        formats the carrier exactly like a delivery method would. The same shipping
        methods are also collected during master data import (see
        `ShopifyAPIClient.get_delivery_methods`), so the carrier can be mapped manually
        and does not depend on the `auto_create_delivery_carrier_on_so` flag.

        For example a marketplace order with an unusable delivery method:

            shippingLine = {
                "id": "gid://shopify/ShippingLine/11959328473463",
                "title": "Amazon Standard",
                "code": "AMZSTD",
                "carrierIdentifier": null,
            }

            delivery_method = {
                "id": "gid://shopify/DeliveryMethod/8332656869751",
                "presentedName": null,
                "methodType": "SHIPPING",
                "serviceCode": null
            }
        """
        shipping_line = self.shipping_line
        delivery_method = self.delivery_method

        carrier, shipping_cost, taxes, note = {}, 0, [], ''
        discount = {}

        if shipping_line:
            use_customer_currency = self.props.use_customer_currency

            # Resolve the carrier. Prefer the fulfillment order's delivery method, but
            # fall back to the shipping line itself for marketplace orders (e.g. Amazon
            # via Marketplace Connect) where the delivery method carries no service code
            # and is therefore not "valid" - yet the order still has a priced shipping
            # line that must not be dropped.
            if delivery_method and delivery_method.is_valid:
                carrier = delivery_method.to_odoo_format()
                if carrier.get('id'):
                    method_type = delivery_method.method_type
                    carrier['is_pickup_point'] = method_type.is_pick_up or method_type.is_pickup_point
            else:
                carrier = self._carrier_from_shipping_line(shipping_line)

            # Use the original (non-discounted) price so that the factory can create
            # proper discount lines for the full discount amount.  Fall back to the
            # current discounted price if originalPriceSet is not available.
            original_price = shipping_line.get_original_price(use_customer_currency)
            shipping_cost = original_price or shipping_line.get_price(use_customer_currency)

            if self.tax_exempt:
                taxes = []
            else:
                taxes = [
                    x.to_odoo_format(self.taxes_included_in_price)
                    for x in shipping_line.tax_lines
                    if not x.is_zero_amount_tax
                ]
            note = self.note or ''

            discount_allocations = shipping_line.discount_allocations
            if discount_allocations:
                parsed_allocations = []
                for allocation in discount_allocations:
                    alloc_amount = allocation.amount_set.get_amount(use_customer_currency)
                    if not alloc_amount:
                        continue
                    parsed_allocations.append({
                        'code': allocation.discount_application,
                        'discount_amount': round(alloc_amount, 4),
                        'discount_amount_tax_incl': 0,
                    })
                if parsed_allocations:
                    total_discount = sum(a['discount_amount'] for a in parsed_allocations)
                    discount_percent = (total_discount / shipping_cost * 100) if shipping_cost else 0
                    discount = {
                        'discount_allocations': parsed_allocations,
                        'discount_amount': total_discount,
                        'discount_percent': discount_percent,
                    }

        return {
            'carrier': carrier,
            'shipping_cost': shipping_cost,
            'taxes': taxes,
            'delivery_notes': note,
            'discount': discount,
        }

    def _carrier_from_shipping_line(self, shipping_line):
        """Build an Odoo carrier dict from the order's shipping line.

        Used as a fallback when the fulfillment order's delivery method is not
        "valid" (no service code / presented name), which happens for marketplace
        orders such as Amazon via Marketplace Connect. In that case the carrier
        identity still lives on the shipping line (`code` / `title`), so we format
        it the same way `DeliveryMethod.to_odoo_format` does to keep the carrier
        mapping code consistent.
        """
        code = shipping_line['code']
        title = shipping_line['title']
        if not code and not title:
            return {}

        name = title or code
        # `format_delivery_code` only relies on the class-level prefix, so calling it
        # on the (empty) DeliveryMethod resource is safe and avoids duplicating logic.
        formatted_code = self._env.DeliveryMethod.format_delivery_code(name, code or name)
        return {'id': formatted_code, 'name': name}

    def parse_order_risks(self):
        self.ensure_one()

        result = self.risk_summary.parse()

        for risk in result:
            risk['order_id'] = self.id_str

        return result

    def parse_payment_transactions(self):
        use_customer_currency = self.props.use_customer_currency
        return [x.to_odoo_format(use_customer_currency) for x in self.transactions]

    def parse_workflow_states(self):
        """
        Order of the `financial_status` (1)
        and `fulfillment_status` (2) matters!!!
        """
        self.ensure_one()

        return [
            self.financial_status.to_odoo_format(),
            self.fulfillment_status.to_odoo_format(),
        ]

    def parse_currency_code(self):
        self.ensure_one()
        return self.presentmentCurrencyCode if self.props.use_customer_currency else self.currencyCode

    def parse_fulfillments(self):
        self.ensure_one()
        return [x.to_odoo_format() for x in self.fulfillments]

    def parse_sale_channel(self):
        self.ensure_one()
        publication = self.publication

        if not publication:
            return None

        return publication.to_odoo_format()

    def parse_customer_data(self):
        self.ensure_one()
        customer = self.customer

        if customer:
            billing = self.billing_address

            if billing:
                billing_data_ = billing.to_odoo_format()
            else:
                billing_data_ = customer.parse_default_address()

            if self.billing_matches_shipping:
                shipping_data_ = billing_data_
            else:
                shipping = self.shipping_address

                if shipping:
                    shipping_data_ = shipping.to_odoo_format()
                else:
                    shipping_data_ = customer.parse_default_address()

            vat_number_field_name = self.props.vat_number_additional_field_name
            personal_id_field_name = self.props.personal_id_additional_field_name

            if billing_data_:
                if vat_number_field_name:
                    billing_data_['company_reg_number'] = self.custom_attributes.get(vat_number_field_name, '')
                if personal_id_field_name:
                    billing_data_['person_id_number'] = self.custom_attributes.get(personal_id_field_name, '')

            if shipping_data_ and not self.billing_matches_shipping:
                if vat_number_field_name:
                    shipping_data_['company_reg_number'] = self.custom_attributes.get(vat_number_field_name, '')
                if personal_id_field_name:
                    shipping_data_['person_id_number'] = self.custom_attributes.get(personal_id_field_name, '')

            customer_data = customer.to_odoo_format()
            billing_data = customer._update_with_defaults(billing_data_, type='invoice')
            shipping_data = customer._update_with_defaults(shipping_data_)
        else:
            customer_data = billing_data = shipping_data = {}

        return {
            'customer': customer_data,
            'billing': billing_data,
            'shipping': shipping_data,
        }


class Order(ShopifyResourceUpdate, MetafieldMixin, OrderParseMixin):

    _gid_name = 'Order'
    _request_name = 'order'
    _body = ShopifyResourceUpdate._tmpl.ORDER_BODY

    ORDER_GET_TAXES_BODY = ShopifyResourceUpdate._tmpl.ORDER_GET_TAXES_BODY
    ORDER_GET_DELIVERY_METHODS_BODY = ShopifyResourceUpdate._tmpl.ORDER_GET_DELIVERY_METHODS_BODY
    ORDER_GET_PAYMENT_METHODS_BODY = ShopifyResourceUpdate._tmpl.ORDER_GET_PAYMENT_METHODS_BODY
    ORDER_INPUT_FILE_BODY = ShopifyResourceUpdate._tmpl.ORDER_INPUT_FILE_BODY

    MUTATION_UPDATE = ShopifyResourceUpdate._tmpl.MUTATION_UPDATE_ORDER
    MUTATION_CANCEL_ORDER = ShopifyResourceUpdate._tmpl.MUTATION_CANCEL_ORDER
    MUTATION_MARK_AS_PAID = ShopifyResourceUpdate._tmpl.MUTATION_MARK_AS_PAID

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        OrderParseMixin.__init__(self, *args, **kwargs)

    def to_odoo_format(self):
        self.ensure_one()
        return {
            'id': self.id_str,
            'data': self.to_dict(),
            'updated_at': self.updated_at,
            'created_at': self.created_at,
        }

    @property
    def is_cancelled(self):
        self.ensure_one()
        return bool(self.cancelledAt)

    @property
    def tax_exempt(self):
        self.ensure_one()
        return bool(self['taxExempt'])

    @property
    def taxes_included_in_price(self):
        self.ensure_one()
        return bool(self['taxesIncluded'])

    @property
    def requires_shipping(self):
        self.ensure_one()
        return self['requiresShipping']

    @property
    def source_name(self):
        self.ensure_one()
        return self['sourceName'] or ''

    @property
    def fulfillment_status(self):
        self.ensure_one()
        status = self['displayFulfillmentStatus']

        if not status:
            return self._env.OrderDisplayFulfillmentStatus('UNFULFILLED')

        return self._env.OrderDisplayFulfillmentStatus(status)

    @property
    def financial_status(self):
        self.ensure_one()
        return self._env.OrderDisplayFinancialStatus(self['displayFinancialStatus'])

    @property
    def risk_summary(self):
        self.ensure_one()
        return self._env.OrderRiskSummary.set(**(self['risk'] or {}))

    @property
    def current_total_price_set(self):
        self.ensure_one()
        return self._env.MoneyBag.set(**(self['currentTotalPriceSet'] or {}))

    @property
    def payment_gateway_names(self):
        self.ensure_one()
        return self.paymentGatewayNames or []

    @property
    def line_items(self):
        self.ensure_one()
        return [self._env.LineItem.set(**x) for x in (self['lineItems'] or [])]

    @property
    def tax_lines(self):
        self.ensure_one()
        return [self._env.TaxLine.set(**x) for x in (self['taxLines'] or [])]

    @property
    def customer(self):
        self.ensure_one()
        return self._env.Customer.set(**(self['customer'] or {}))

    @property
    def transactions(self):
        self.ensure_one()
        return [self._env.OrderTransaction.set(**x) for x in (self['transactions'] or [])]

    @property
    def fulfillment_orders(self):
        self.ensure_one()

        if not self.key_exist('fulfillmentOrders'):
            self.get_fulfillment_orders()

        return [self._env.FulfillmentOrder.set(**x) for x in (self['fulfillmentOrders'] or [])]

    @property
    def fulfillments(self):
        self.ensure_one()

        if not self.key_exist('fulfillments'):
            self.get_fulfillments()

        return [self._env.Fulfillment.set(**x) for x in (self['fulfillments'] or [])]

    @property
    def shipping_line(self):
        self.ensure_one()
        return self._env.ShippingLine.set(**(self['shippingLine'] or {}))

    @property
    def shipping_lines(self):
        self.ensure_one()
        return [self._env.ShippingLine.set(**x) for x in (self['shippingLines'] or [])]

    @property
    def billing_address(self):
        self.ensure_one()
        return self._env.MailingAddress.set(**(self['billingAddress'] or {}))

    @property
    def shipping_address(self):
        self.ensure_one()
        return self._env.MailingAddress.set(**(self['shippingAddress'] or {}))

    @property
    def delivery_method(self):
        self.ensure_one()

        fulfillment_orders = self.fulfillment_orders
        default_delivery_method = self._env.DeliveryMethod

        # If there is no fulfillment orders, return the default delivery method.
        if not fulfillment_orders:
            return default_delivery_method

        # Parse available delivery methods.
        delivery_methods = [x.delivery_method for x in fulfillment_orders]

        # Sort delivery methods by validity (it means the valid ones are first).
        delivery_methods.sort(key=lambda x: x.is_valid, reverse=True)

        # If the delivery_methods variable is an empty or all the delivery methods are Falsy or invalid,
        # return the default delivery method.
        if all(not x for x in delivery_methods) or all(not x.is_valid for x in delivery_methods):
            return default_delivery_method

        # If there is only one delivery method, return it.
        delivery_method_first = delivery_methods[0]
        if len(delivery_methods) == 1:
            return delivery_method_first
        # If all the delivery methods have the same code, return the first delivery method.
        elif len(set([x.code for x in delivery_methods])) == 1:
            return delivery_method_first
        # If all the delivery methods have the same name, return the first delivery method.
        elif len(set([x.name for x in delivery_methods])) == 1:
            return delivery_method_first

        # If there are multiple fulfillment orders, return the delivery method
        # of the fulfillment order with the appropriate shipping code.
        shipping_line = self.shipping_line

        shipping_code = shipping_line['code']
        shipping_name = shipping_line['title']

        # If the shipping code is not set, return the first valid delivery method.
        if not shipping_code and not shipping_name:
            return delivery_method_first

        # Return the delivery method with the appropriate shipping code.
        delivery_method = next(
            filter(lambda x: x.code == shipping_code, delivery_methods),
            None,
        )

        # If the delivery method is not found by shipping code, try to find it by the shipping line title.
        if not delivery_method and shipping_name:
            delivery_method = next(
                filter(lambda x: x.name == shipping_name, delivery_methods),
                None,
            )

        # If the delivery method is not found by shipping code, return the first valid delivery method.
        if not delivery_method:
            raise self._es.ValidationError(
                'Delivery method may not be parsed. Please contact VentorTech support '
                'at support@ventor.tech to report this issue.',
            )

        return delivery_method

    @property
    def publication(self):
        self.ensure_one()
        return self._env.Publication.set(**(self['publication'] or {}))

    @property
    def custom_attributes(self):
        self.ensure_one()
        return {x['key']: x['value'] for x in (self['customAttributes'] or [])}

    @property
    def location_id(self):
        self.ensure_one()
        fulfillment_orders = self.fulfillment_orders

        if len(fulfillment_orders) != 1:
            return False

        return fulfillment_orders[0].location.id_str

    @property
    def billing_matches_shipping(self):
        self.ensure_one()
        return self.billingAddressMatchesShippingAddress

    @property
    def business_entity(self):
        self.ensure_one()
        return self._env.BusinessEntity.set(**(self['merchantBusinessEntity'] or {}))

    def get_batch_body_minimal(self, filter_params: str = ''):
        return self.get_batch(
            body=self.ORDER_INPUT_FILE_BODY,
            arguments='sortKey: UPDATED_AT',
            filter_params=filter_params,
        )

    def get_batch_for_payment_methods(self):
        return self.get_batch(
            body=self.ORDER_GET_PAYMENT_METHODS_BODY,
            arguments='sortKey: ID, reverse: true',
        )

    def get_batch_for_taxes(self):
        return self.get_batch(
            body=self.ORDER_GET_TAXES_BODY,
            arguments='sortKey: ID, reverse: true',
        )

    def get_batch_for_delivery_methods(self):
        return self.get_batch(
            body=self.ORDER_GET_DELIVERY_METHODS_BODY,
            arguments='sortKey: ID, reverse: true',
        )

    def update(self, **kwargs: dict) -> bool:
        self.ensure_one()

        response = self.execute(
            self.MUTATION_UPDATE,
            variables={
                'input': {
                    'id': self.gid,
                    **kwargs,
                },
            },
            user_errors_path='data.orderUpdate.userErrors',
        )

        result = self._extract(response, 'data.orderUpdate.order', dict)
        self.set(**result)

        return True

    def cancel(self, *args):
        self.ensure_one()

        response = self.execute(
            self.MUTATION_CANCEL_ORDER % (self.id, *args),
            user_errors_path='data.orderCancel.orderCancelUserErrors',
        )

        result = self._extract(response, 'data.orderCancel.job', dict)

        return result

    def _get_order_line_by_id(self, line_id: str):
        return {x.id_str: x for x in self.order_line_items}[line_id]

    def _get_available_line_qty(self, line_id):
        return sum(self._line_qty.get(line_id, []))

    def _group_lines_by_location(self):
        result = []
        for f_order in self.fulfillment_orders:
            if f_order.is_cancelled or not f_order.line_items:
                continue

            line_items = f_order.line_items

            if f_order.is_closed:
                if f_order.closed_before_fulfill:
                    continue
                line_items = filter(lambda x: not x.remaining_quantity, line_items)

            items = [(x.sale_line_item.id_str, x.total_quantity) for x in line_items if x.total_quantity]

            if items:
                result.append((f_order.location.id_str, items))

        return result

    def get_fulfillment_orders(self, open_or_in_progress=False):
        self.ensure_one()

        body = 'id fulfillmentOrders(first: 25) { nodes { %s } }' % self._env.FulfillmentOrder.default_body()
        result = self.read(body=body, return_raw=True)

        self.set(fulfillmentOrders=result['fulfillmentOrders'])

        orders = self.fulfillment_orders

        if open_or_in_progress:
            return [x for x in orders if x.status.open_or_in_progress and x.line_items]

        return orders

    def get_fulfillments(self):
        self.ensure_one()

        body = 'id fulfillments(first: 25) { %s }' % self._env.Fulfillment.default_body()
        result = self.read(body=body, return_raw=True)

        self.set(fulfillments=result['fulfillments'])

        return self.fulfillments

    def mark_as_paid(self):
        self.ensure_one()

        response = self.execute(
            self.MUTATION_MARK_AS_PAID,
            variables={
                'input': {
                    'id': self.gid,
                },
            },
            user_errors_path='data.orderMarkAsPaid.userErrors',
        )

        result = self._extract(response, 'data.orderMarkAsPaid.order', dict)
        self.set(**result)

        return True
