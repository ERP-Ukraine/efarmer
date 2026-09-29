# See LICENSE file for full copyright and licensing details.

from copy import deepcopy

from .base import ShopifyResourceRead
from .metafields_mixin import MetafieldMixin


class Customer(ShopifyResourceRead, MetafieldMixin):

    _gid_name = 'Customer'
    _request_name = 'customer'
    _body = ShopifyResourceRead._tmpl.CUSTOMER_BODY

    @property
    def first_name(self):
        self.ensure_one()
        return self['firstName'] or ''

    @property
    def last_name(self):
        self.ensure_one()
        return self['lastName'] or ''

    @property
    def state(self):
        self.ensure_one()
        return self._env.CustomerState(self['state']).to_odoo_format()

    def get_addresses(self):
        """Every address on the customer.

        The embedded page is capped at CUSTOMER_ADDRESSES_PAGE_SIZE to keep
        each customer query cheap (Shopify bills by the requested page size,
        not by what actually comes back). A full page is the only sign there
        may be more -- when it happens, page through a dedicated query
        against this one customer instead. Cached after the first call so a
        repeated call does not refetch, the same way InventoryItem.get_variants()
        does for the same reason: a full page can also legitimately be the
        real, complete count.
        """
        self.ensure_one()

        if not self.ctx('addresses_fetched', bool):
            nodes = self['addressesV2'] or []

            if len(nodes) == self._tmpl.CUSTOMER_ADDRESSES_PAGE_SIZE:
                nodes = self._fetch_all_address_nodes()

            self.set(addressesV2=nodes)
            self.add_context(addresses_fetched=True)

        return [self._env.MailingAddress.set(**values) for values in (self['addressesV2'] or [])]

    def _fetch_all_address_nodes(self):
        query = '''
            query($id: ID!, $cursor: String) {
                customer(id: $id) {
                    addressesV2(first: 250, after: $cursor) {
                        nodes {
                            %s
                        }
                        pageInfo {
                            endCursor
                            hasNextPage
                        }
                    }
                }
            }
        ''' % self._tmpl.MAILING_ADDRESS_BODY
        nodes = []
        cursor = None

        while True:
            response = self.execute(query, variables={'id': self.gid, 'cursor': cursor})
            data = self._extract(response, 'data.customer.addressesV2', dict) or {}
            nodes.extend(data.get('nodes') or [])

            page_info = data.get('pageInfo') or {}
            if not page_info.get('hasNextPage'):
                break
            cursor = page_info.get('endCursor')

        return nodes

    @property
    def display_name(self):
        self.ensure_one()
        return (self.displayName or self.email).strip()

    @property
    def default_address(self):
        self.ensure_one()
        return self._filter_address(self.default_address_str_id)

    @property
    def default_address_str_id(self):
        self.ensure_one()

        if not self['defaultAddress']:
            return ''

        return self.parse_int_to_str(self.defaultAddress['id'])

    @property
    def email(self):
        self.ensure_one()
        data = self['defaultEmailAddress'] or {}

        return (data.get('emailAddress') or '') if isinstance(data, dict) else ''

    @property
    def phone(self):
        self.ensure_one()
        data = self['defaultPhoneNumber'] or {}

        return (data.get('phoneNumber') or '') if isinstance(data, dict) else ''

    @property
    def locale(self):
        self.ensure_one()
        return self['locale'] or ''

    def parse(self):
        addresses = [x.to_odoo_format() for x in self.get_addresses()]
        return self.to_odoo_format(), [self._update_with_defaults(x) for x in addresses]

    def parse_default_address(self):
        self.ensure_one()

        customer = self.to_odoo_format()

        if not self.default_address or not self.get_addresses():
            return {}

        return {**customer, **self.default_address.to_odoo_format()}

    def to_odoo_format(self):
        self.ensure_one()
        return {
            'id': self.id_str,
            'email': self.email,
            'phone': self.phone,
            'person_name': self.display_name,
            'customer_locale': self.locale
        }

    def _update_with_defaults(self, values: dict, **kwargs) -> dict:
        defaults = self.to_odoo_format()

        values_ = deepcopy(values)

        # 1. Duplicate language from customer to address if available
        values_['customer_locale'] = defaults['customer_locale']

        # 2. Fallback to customer name if name is missing
        if not values_.get('person_name'):
            values_['person_name'] = defaults['person_name']

        # 3. Fallback to customer email if email is missing
        if not values_.get('email'):
            values_['email'] = defaults['email']

        # 4. Determine the address type as “invoice”.
        # Since in Shopify one address can be set as both billing and shipping addresses.
        # We only need the billing address
        if values_.get('id') == self.default_address_str_id:
            values_['default'] = True

        values_.update(kwargs)

        return values_

    def _filter_address(self, address_id: str):
        if not address_id:
            return None

        result = list(filter(lambda x: x.id_str == address_id, self.get_addresses()))

        if not result:
            raise ValueError(f'Address with id={address_id} not found')

        return result[0]
