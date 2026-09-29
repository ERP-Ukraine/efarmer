# See LICENSE file for full copyright and licensing details.

from .base import ShopifyResourceRead


class ShopifyPaymentsAccount(ShopifyResourceRead):
    """Singleton Shopify Payments account.

    Selects only id and defaultCurrency. Do NOT add payoutSchedule / balance / country /
    activated — an unavailable field nulls the entire shopifyPaymentsAccount object
    (verified live: payoutSchedule → BAD_REQUEST → account null).
    """

    _gid_name = 'ShopifyPaymentsAccount'
    _request_name = 'shopifyPaymentsAccount'
    _body = ShopifyResourceRead._tmpl.SHOPIFY_PAYMENTS_ACCOUNT_BODY

    def get_current(self):
        """Fetch the singleton account (no id argument)."""
        query = '{ %s { %s } }' % (self._request_name, self.default_body())
        response = self.execute(query)
        data = self._extract(response, f'data.{self._request_name}', dict) or {}
        self.set(**data)
        return self

    @property
    def default_currency(self) -> str | bool:
        self.ensure_one()
        return self['defaultCurrency']

    def to_odoo_format(self) -> dict:
        return {
            'external_str_id': self.id_str,
            'default_currency': self.default_currency,
        }
