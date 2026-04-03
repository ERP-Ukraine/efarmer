# See LICENSE file for full copyright and licensing details.

import re

from .base import GqlDict


class TaxLine(GqlDict):

    _gid_name = 'TaxLine'
    _body = GqlDict._tmpl.TAX_LINE_BODY

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._set_pseudo_id()

    @property
    def rate_percentage(self):
        self.ensure_one()
        return self.ratePercentage

    @property
    def is_zero_amount_tax(self):
        """Return True if this tax has a non-zero rate but zero amount.

        Shopify occasionally keeps tax lines on order lines or shipping with a
        positive rate (e.g. 6%) but a zero amount.  Applying such a tax in Odoo
        would produce a non-zero tax amount and cause an order total mismatch.
        """
        self.ensure_one()
        if not float(self['rate'] or 0):
            return False
        price_set = self['priceSet'] or {}
        shop_money = price_set.get('shopMoney') or {}
        return float(shop_money.get('amount') or 0) == 0.0

    def to_odoo_format(self, taxes_included: bool):
        self.ensure_one()
        # Format tax as 'Sales Tax (LX799/XL) 20.3% [excluded]'
        tax_option = 'included' if taxes_included else 'excluded'
        return f'{self.title} {self.rate_percentage}% [{tax_option}]'

    @staticmethod
    def parse_formatted_tax(name):
        # Expected tax_id formatted as 'Sales Tax (LX799/XL) 20.3% [excluded]'
        tax_rate = re.findall(r'-?\d+\.?\d*', name)[-1]  # parse `20.3`
        tax_option = re.findall(r'\[(\w+)\]', name)[-1]  # parse `excluded`

        return {
            'id': name,
            'name': name,
            'rate': tax_rate,
            'price_include': {'excluded': False, 'included': True}[tax_option],
        }
