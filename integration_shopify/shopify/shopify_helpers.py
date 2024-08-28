#  See LICENSE file for full copyright and licensing details.

MIN_API_VERSION = 202204

REQUIRED_SCOPES = (
    'read_locations',
    'read_customers',
    'read_products',
    'write_products',
    'read_orders',
    'write_orders',
    'read_inventory',
    'write_inventory',
    'write_fulfillments',
    'read_fulfillments',
    'read_merchant_managed_fulfillment_orders',
    'write_merchant_managed_fulfillment_orders',
    'read_publications',
)


class ShopifyOrderStatus:
    """
    The ShopifyOrderStatus class contains order statuses that can be used both for querying the store's API
    and for using them during order parsing. It's worth noting that they often have
    different names but mean the same thing. For example, the "shipped" status in a request
    will correspond to the "fulfilled" status in the response. Similarly, the "unshipped"
    or "unfulfilled" status in a request will correspond to "null" or "null + partial" statuses
    in the response.
    """

    STATUS_AUTHORIZED = 'authorized'
    STATUS_PENDING = 'pending'
    STATUS_PAID = 'paid'
    STATUS_PARTIALLY_PAID = 'partially_paid'
    STATUS_REFUNDED = 'refunded'
    STATUS_VOIDED = 'voided'
    STATUS_PARTIALLY_REFUNDED = 'partially_refunded'
    STATUS_UNPAID = 'unpaid'

    STATUS_PARTIAL = 'partial'
    STATUS_FULFILLED = 'fulfilled'
    STATUS_RESTOCKED = 'restocked'
    STATUS_UNSHIPPED = 'unshipped'
    STATUS_UNFULFILLED = 'unfulfilled'

    STATUS_OPEN = 'open'
    STATUS_CLOSED = 'closed'
    STATUS_CANCELLED = 'cancelled'

    SPECIAL_STATUS_ANY = 'any'
    SPECIAL_STATUS_SHIPPED = 'shipped'

    _financial_status_data = {
        STATUS_AUTHORIZED: (
            'Authorized',
            'The payments have been authorized.',
        ),
        STATUS_PENDING: (
            'Pending',
            'The payments are pending. Payment might fail in this state. '
            'Check again to confirm whether the payments have been paid successfully.',
        ),
        STATUS_PAID: (
            'Paid',
            'The payments have been paid.',
        ),
        STATUS_PARTIALLY_PAID: (
            'Partially Paid',
            'The order has been partially paid.',
        ),
        STATUS_REFUNDED: (
            'Refunded',
            'The payments have been refunded.',
        ),
        STATUS_VOIDED: (
            'Voided',
            'The payments have been voided.',
        ),
        STATUS_PARTIALLY_REFUNDED: (
            'Partially Refunded',
            'The payments have been partially refunded.',
        ),
        STATUS_UNPAID: (
            'Unpaid',
            'Receive authorized and partially paid orders.',
        ),
    }

    _fulfillment_status_data = {
        STATUS_FULFILLED: (  # !!! In Shopify API this parameter named as `shipped`
            'Shipped',  # howewer in received order it named `fulfilled` and we need to have the
            'Receive orders that have been shipped. '  # mapping object exactly as `fulfilled`
            'Returns orders with fulfillment_status of fulfilled.',
        ),
        STATUS_PARTIAL: (
            'Partial',
            'Receive partially shipped orders.'
        ),
        STATUS_UNSHIPPED: (
            'Unshipped',
            'Receive orders that have not yet been shipped. '
            'Returns orders with fulfillment_status of null.',
        ),
        STATUS_UNFULFILLED: (
            'Unfulfilled',
            'Receive orders with fulfillment_status of null or partial.',
        ),
    }

    _fulfillment_status_restocked_data = {
        STATUS_RESTOCKED: (
            'Restocked',
            'Every line item in the order has been restocked and the order canceled.',
        ),
    }

    _any_status_data = {
        SPECIAL_STATUS_ANY: (
            'Any',
            'Receive orders of any status.',
        ),
    }

    _order_status_data = {
        STATUS_OPEN: (
            'Open',
            'Receive only open orders.'
        ),
        STATUS_CLOSED: (
            'Closed',
            'Receive only closed orders.',
        ),
        STATUS_CANCELLED: (
            'Cancelled',
            'Receive only cancelled orders.',
        ),
    }

    @classmethod
    def order_statuses(cls):
        return {
            **cls._any_status_data,
            **cls._order_status_data,
        }

    @classmethod
    def financial_statuses(cls):
        return {
            **cls._any_status_data,
            **cls._financial_status_data,
        }

    @classmethod
    def fulfillment_statuses(cls):
        return {
            **cls._any_status_data,
            **cls._fulfillment_status_data,
        }

    @classmethod
    def all_statuses(cls):
        return {
            **cls._any_status_data,
            **cls._order_status_data,
            **cls._financial_status_data,
            **cls._fulfillment_status_data,
            **cls._fulfillment_status_restocked_data,
        }


class ShopifyTxnStatus:
    """The ShopifyTxn class contains Shopify Transaction statuses"""

    SALE = 'sale'
    VOID = 'void'
    AUTH = 'authorization'
    CAPTURE = 'capture'
    STATUS_SUCCESS = 'success'
    STATUS_PENDING = 'pending'
    SOURCE_EXTERNAL = 'external'
