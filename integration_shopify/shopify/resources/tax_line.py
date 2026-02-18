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
