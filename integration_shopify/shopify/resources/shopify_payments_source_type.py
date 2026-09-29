# See LICENSE file for full copyright and licensing details.

from .status_abstract import StatusAbstract


# ShopifyPaymentsSourceType — closed set (Admin GraphQL 2026-04).
# https://shopify.dev/docs/api/admin-graphql/2026-04/enums/ShopifyPaymentsSourceType
SOURCE_TYPE_MAP = {
    'ADJUSTMENT': ('Adjustment', 'The adjustment source type.'),
    'ADJUSTMENT_REVERSAL': ('Adjustment Reversal', 'The adjustment_reversal source type.'),
    'CHARGE': ('Charge', 'The charge source type.'),
    'DISPUTE': ('Dispute', 'The dispute source type.'),
    'REFUND': ('Refund', 'The refund source type.'),
    'SYSTEM_ADJUSTMENT': ('System Adjustment', 'The system_adjustment source type.'),
    'TRANSFER': ('Transfer', 'The transfer source type.'),
}


class ShopifyPaymentsSourceType(StatusAbstract):
    """ShopifyPaymentsSourceType — GraphQL uppercase value, Odoo name via ``to_odoo_format``."""

    adjustment = 'ADJUSTMENT'
    adjustment_reversal = 'ADJUSTMENT_REVERSAL'
    charge = 'CHARGE'
    dispute = 'DISPUTE'
    refund = 'REFUND'
    system_adjustment = 'SYSTEM_ADJUSTMENT'
    transfer = 'TRANSFER'

    @property
    def mapping(self):
        return SOURCE_TYPE_MAP

    @classmethod
    def _missing_(cls, value):
        """Forward-compat: Shopify may add source types; store as Char via member name."""
        if isinstance(value, str) and value:
            obj = object.__new__(cls)
            obj._name_ = value.lower()
            obj._value_ = value
            return obj
        return None
