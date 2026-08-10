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

    def is_rate_amount_mismatch(self, taxable_base):
        """Return True if this tax's rate contradicts its own computed tax amount.

        Shopify occasionally keeps a tax line with a positive rate (e.g. 6%) but
        a zero tax amount even though the line it belongs to has a non-zero
        taxable base. Applying such a tax in Odoo would produce a non-zero tax
        amount and cause an order total mismatch, so it must be dropped.

        The base must be the amount Shopify itself computed the tax on, i.e. the
        line total *after* discount allocations - not the original price. With no
        positive base (free line, or one discounted down to zero) a zero tax
        amount is correct, not a mismatch: any rate applied to 0 is 0.
        """
        self.ensure_one()
        if float(taxable_base or 0) <= 0:
            return False

        rate = float(self['rate'] or 0)
        shop_money = (self['priceSet'] or {}).get('shopMoney') or {}
        tax_amount = float(shop_money.get('amount') or 0)

        return bool(rate) and not bool(tax_amount)

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
