# See LICENSE file for full copyright and licensing details.

from .base import GqlDict


class OrderTransaction(GqlDict):

    _gid_name = 'OrderTransaction'
    _request_name = 'orderTransaction'
    _body = GqlDict._tmpl.ORDER_TRANSACTION_BODY

    PAYMENT_NOT_DEFINED = 'Not_Defined'
    SHOPIFY_PAYMENT_PREF = 'shopify-payment-'

    @property
    def name(self):
        self.ensure_one()
        return f'[ID={self.id}] {self.gateway}'

    @property
    def order(self):
        self.ensure_one()
        return self._env.Order.set(**(self['order'] or {}))

    @property
    def status(self):
        self.ensure_one()
        return self._env.OrderTransactionStatus(self['status'])

    @property
    def kind(self):
        self.ensure_one()
        return self._env.OrderTransactionKind(self['kind'])

    @property
    def payment_id(self):
        self.ensure_one()
        return self.paymentId or False

    @property
    def parent_transaction(self):
        self.ensure_one()
        return self._new(**(self.parentTransaction or {}))

    @property
    def gateway(self):
        self.ensure_one()
        return self['gateway'] or ''

    @property
    def gateway_fmt(self):
        return self.cls.format_payment_code(self.gateway)

    @property
    def amount_set(self):
        self.ensure_one()
        return self._env.MoneyBag.set(**(self['amountSet'] or {}))

    @property
    def processed_at(self):
        self.ensure_one()
        return self.processedAt

    def to_odoo_format(self, use_customer_currency=False):
        self.ensure_one()
        return dict(
            name=self.name,
            kind=self.kind.to_odoo_format(),
            amount=self.amount_set.get_amount(use_customer_currency),
            gateway=self.gateway_fmt,
            currency=self.amount_set.get_currency(use_customer_currency),
            external_str_id=self.id_str,
            external_status=self.status.to_odoo_format(),
            external_order_str_id=self.order.id_str,
            external_parent_str_id=self.parent_transaction.id_str,
            external_process_date=self.processed_at,
            transaction=self.payment_id,
        )

    @classmethod
    def format_payment_code(cls, name):
        if name:
            return f'{cls.SHOPIFY_PAYMENT_PREF}{name}'
        return f'{cls.SHOPIFY_PAYMENT_PREF}{cls.PAYMENT_NOT_DEFINED}'
