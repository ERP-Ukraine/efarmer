# See LICENSE file for full copyright and licensing details.

from .status_abstract import StatusAbstract


CUSTOMER_STATE_MAP = {
    'DECLINED': ('Declined', 'The customer declined the email invite to create an account.'),
    'DISABLED': (
        'Disabled',
        'The customer doesn\'t have an active account. '
        'Customer accounts can be disabled from the Shopify admin at any time.'
    ),
    'ENABLED': (
        'Enabled',
        'The customer has created an account.'
    ),
    'INVITED': (
        'Invited', 'The customer has received an email invite to create an account.'),
}


class CustomerState(StatusAbstract):

    declined = 'DECLINED'
    disabled = 'DISABLED'
    enabled = 'ENABLED'
    invited = 'INVITED'

    @property
    def is_declined(self):
        return self == self.declined

    @property
    def is_disabled(self):
        return self == self.disabled

    @property
    def is_enabled(self):
        return self == self.enabled

    @property
    def is_invited(self):
        return self == self.invited

    @property
    def mapping(self):
        return CUSTOMER_STATE_MAP
