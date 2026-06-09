# See LICENSE file for full copyright and licensing details.

from .status_abstract import StatusAbstract


TRANSACTION_KIND_MAP = {
    'AUTHORIZATION': ('Authorization', 'An amount reserved against the cardholder\'s funding source.'),
    'CAPTURE': ('Capture', 'A transfer of the money that was reserved by an authorization.'),
    'CHANGE': ('Change', 'The money returned to the customer when they\'ve paid too much during a cash transaction.'),
    'EMV_AUTHORIZATION': ('EMV Authorization', 'An authorization for a payment taken with an EMV credit card reader.'),
    'REFUND': ('Refund', 'A partial or full return of captured funds to the cardholder.'),
    'SALE': ('Sale', 'A sale transaction.'),
    'SALE_AUTHORIZATION': ('Sale Authorization', 'An authorization and capture performed together in a single step.'),
    'SUGGESTED_REFUND': ('Suggested Refund', 'A suggested refund transaction that can be used to create a refund.'),
    'VOID': ('Void', 'A cancelation of an authorization transaction.'),
}


class OrderTransactionKind(StatusAbstract):

    authorization = 'AUTHORIZATION'
    capture = 'CAPTURE'
    change = 'CHANGE'
    emv_authorization = 'EMV_AUTHORIZATION'
    refund = 'REFUND'
    sale = 'SALE'
    sale_authorization = 'SALE_AUTHORIZATION'
    suggested_refund = 'SUGGESTED_REFUND'
    void = 'VOID'

    @property
    def is_authorization(self):
        return self == self.authorization

    @property
    def is_capture(self):
        return self == self.capture

    @property
    def is_change(self):
        return self == self.change

    @property
    def is_emv_authorization(self):
        return self == self.emv_authorization

    @property
    def is_refund(self):
        return self == self.refund

    @property
    def is_sale(self):
        return self == self.sale

    @property
    def is_sale_authorization(self):
        return self == self.sale_authorization

    @property
    def is_suggested_refund(self):
        return self == self.suggested_refund

    @property
    def is_void(self):
        return self == self.void

    @property
    def mapping(self):
        return TRANSACTION_KIND_MAP
