# See LICENSE file for full copyright and licensing details.

from .base import GqlDict


class LineItem(GqlDict):

    _gid_name = 'LineItem'
    _body = GqlDict._tmpl.LINE_ITEM_BODY

    @property
    def name(self):
        self.ensure_one()
        return self['name'] or ''

    @property
    def sku(self):
        self.ensure_one()
        return self['sku'] or ''

    @property
    def product(self):
        self.ensure_one()
        return self._env.Product.set(**(self['product'] or {}))

    @property
    def variant(self):
        self.ensure_one()
        return self._env.ProductVariant.set(**(self['variant'] or {}))

    @property
    def is_gift_card(self):
        return self['isGiftCard']

    @property
    def original_unit_price_set(self):
        self.ensure_one()
        return self._env.MoneyBag.set(**(self['originalUnitPriceSet'] or {}))

    @property
    def current_quantity(self):
        self.ensure_one()
        return self['currentQuantity'] or 0

    @property
    def tax_lines(self):
        self.ensure_one()
        return [self._env.TaxLine.set(**x) for x in (self['taxLines'] or [])]

    @property
    def discount_allocations(self):
        self.ensure_one()
        return [self._env.DiscountAllocation.set(**x) for x in (self['discountAllocations'] or [])]

    @property
    def non_fulfillable_quantity(self):
        self.ensure_one()
        return self['nonFulfillableQuantity'] or 0


class OrderLineItem(LineItem):
    """Class used exclusively in the OrderParseMixin to parse the line items."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._order = None  # Instance of the Order class

    def ensure_one(self):
        super().ensure_one()

        if not self._order:
            raise ValueError('Order is required')

    @property
    def order(self):
        return self._order

    @property
    def props(self):
        self.ensure_one()
        return self.order.props

    @property
    def price(self):
        self.ensure_one()
        money_bag = self.original_unit_price_set
        return money_bag.get_amount(self.props.use_customer_currency)

    @property
    def price_tax_incl(self):
        self.ensure_one()
        return self.price if self.order.taxes_included_in_price else 0

    @property
    def current_quantity_tmp(self):
        self.ensure_one()

        if not self.key_exist('current_quantity_tmp'):
            self.set(current_quantity_tmp=self.current_quantity)

        return self['current_quantity_tmp']

    def parse(self, requested_quantity):
        self.ensure_one()

        variant = self.variant

        if self.order.tax_exempt:
            taxes = []
        else:
            taxes = [
                x.to_odoo_format(self.order.taxes_included_in_price)
                for x in self.tax_lines
                if not x.is_zero_amount_tax
            ]

        result = {
            'id': self.id_str,
            'name': self.name,
            'reference': self.sku,
            'price_unit': self.price,
            'product_uom_qty': requested_quantity,
            'product_id': variant and variant.external_id or None,
            'price_unit_tax_incl': self.price_tax_incl,
            'taxes': taxes,
            'discount': {},
        }

        discount_allocations = self.discount_allocations

        if discount_allocations:
            use_customer_currency = self.props.use_customer_currency
            current_quantity = self.current_quantity

            if not current_quantity:
                return result

            amount = sum(x.amount_set.get_amount(use_customer_currency) for x in discount_allocations)

            if amount:
                amount_ = round(amount * requested_quantity / current_quantity, 4)

                result['discount'].update(
                    discount_amount=amount_,
                    discount_percent=100 * amount_ / (self.price or 1) / (requested_quantity or 1),
                    discount_amount_tax_incl=0,
                )

            # Always populate per-code breakdown so the factory can create
            # separate discount lines when `multiple_discount_lines` is enabled.
            # The factory uses the aggregate `discount` dict when the feature is off.
            discount_allocations_data = []
            for allocation in discount_allocations:
                alloc_amount = allocation.amount_set.get_amount(use_customer_currency)
                if not alloc_amount:
                    continue
                discount_allocations_data.append({
                    'code': allocation.discount_application,
                    'discount_amount': round(alloc_amount * requested_quantity / current_quantity, 4),
                    'discount_amount_tax_incl': 0,
                })
            result['discount']['discount_allocations'] = discount_allocations_data

        return result
