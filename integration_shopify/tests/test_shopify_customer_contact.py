# See LICENSE file for full copyright and licensing details.

import re
from unittest.mock import patch

from odoo.tests import tagged, TransactionCase

from odoo.addons.integration_shopify.shopify.connection import ClientOptions
from odoo.addons.integration_shopify.shopify.graphql_templates import GraphQLTemplate
from odoo.addons.integration_shopify.shopify.resources.customer import Customer
from odoo.addons.integration_shopify.shopify.shopify_graphql import ShopifyGraphQL


@tagged('post_install', '-at_install')
class TestShopifyCustomerContact(TransactionCase):
    """Customer contact must use 2026-07 fields, not deprecated email/phone/addresses."""

    ADDRESS_GID = 'gid://shopify/MailingAddress/11?model_name=CustomerAddress'
    ADDRESS = {
        'id': ADDRESS_GID,
        'firstName': 'Jane',
        'lastName': 'Doe',
        'phone': '+48999',
        'address1': 'Main 1',
        'address2': '',
        'city': 'Warsaw',
        'company': 'Acme',
        'country': 'Poland',
        'countryCodeV2': 'PL',
        'provinceCode': None,
        'zip': '00-001',
    }

    def _gql(self):
        return ShopifyGraphQL(
            'shopifytestsite.myshopify.com',
            'shpat_test',
            '2026-07',
            False,
            ClientOptions(),
        )

    def test_customer_body_uses_replacement_contact_fields(self):
        body = GraphQLTemplate.CUSTOMER_BODY

        self.assertIn('defaultEmailAddress', body)
        self.assertIn('emailAddress', body)
        self.assertIn('defaultPhoneNumber', body)
        self.assertIn('phoneNumber', body)
        self.assertIn('addressesV2(first: 10)', body)
        self.assertNotIn('addresses {', body)
        self.assertIsNone(re.search(r'^\s+email\s*$', body, re.M))

    def test_parse_default_email_phone_and_addresses_v2(self):
        customer = self._gql().Customer.set(
            id='gid://shopify/Customer/1',
            firstName='Jane',
            lastName='Doe',
            displayName='Jane Doe',
            locale='pl',
            defaultEmailAddress={'emailAddress': 'jane@example.com'},
            defaultPhoneNumber={'phoneNumber': '+48111'},
            addressesV2={'nodes': [self.ADDRESS]},
            defaultAddress={'id': self.ADDRESS_GID},
        )

        self.assertEqual(customer.email, 'jane@example.com')
        self.assertEqual(customer.phone, '+48111')
        self.assertEqual(len(customer.get_addresses()), 1)
        self.assertEqual(customer.get_addresses()[0].id_str, '11')
        self.assertEqual(customer.default_address.id_str, '11')
        self.assertEqual(customer.to_odoo_format(), {
            'id': '1',
            'email': 'jane@example.com',
            'phone': '+48111',
            'person_name': 'Jane Doe',
            'customer_locale': 'pl',
        })

        customer_data, addresses = customer.parse()
        self.assertEqual(customer_data['email'], 'jane@example.com')
        self.assertEqual(len(addresses), 1)
        self.assertTrue(addresses[0]['default'])
        self.assertEqual(addresses[0]['email'], 'jane@example.com')

    def test_missing_contact_objects_are_empty(self):
        customer = self._gql().Customer.set(
            id='gid://shopify/Customer/2',
            displayName='Guest',
            defaultEmailAddress=None,
            defaultPhoneNumber=None,
            addressesV2={'nodes': []},
            defaultAddress=None,
        )

        self.assertEqual(customer.email, '')
        self.assertEqual(customer.phone, '')
        self.assertEqual(customer.get_addresses(), [])
        self.assertFalse(customer.default_address)
        self.assertEqual(customer.parse(), (
            {
                'id': '2',
                'email': '',
                'phone': '',
                'person_name': 'Guest',
                'customer_locale': '',
            },
            [],
        ))

    def _address(self, address_id):
        return {**self.ADDRESS, 'id': f'gid://shopify/MailingAddress/{address_id}?model_name=CustomerAddress'}

    def test_short_page_does_not_trigger_a_follow_up_query(self):
        customer = self._gql().Customer.set(
            id='gid://shopify/Customer/3',
            addressesV2={'nodes': [self._address(1)]},
        )

        with patch.object(Customer, 'execute') as execute_mock:
            addresses = customer.get_addresses()

        execute_mock.assert_not_called()
        self.assertEqual([a.id_str for a in addresses], ['1'])

    def test_full_page_triggers_a_paginated_follow_up_query(self):
        page_size = GraphQLTemplate.CUSTOMER_ADDRESSES_PAGE_SIZE
        customer = self._gql().Customer.set(
            id='gid://shopify/Customer/4',
            addressesV2={'nodes': [self._address(i) for i in range(page_size)]},
        )

        first_page = {'data': {'customer': {'addressesV2': {
            'nodes': [self._address(100)],
            'pageInfo': {'endCursor': 'cursor1', 'hasNextPage': True},
        }}}}
        second_page = {'data': {'customer': {'addressesV2': {
            'nodes': [self._address(200)],
            'pageInfo': {'endCursor': None, 'hasNextPage': False},
        }}}}

        with patch.object(Customer, 'execute', side_effect=[first_page, second_page]) as execute_mock:
            addresses = customer.get_addresses()

        self.assertEqual(execute_mock.call_count, 2)
        self.assertIsNone(execute_mock.call_args_list[0].kwargs['variables']['cursor'])
        self.assertEqual(execute_mock.call_args_list[1].kwargs['variables']['cursor'], 'cursor1')
        self.assertEqual([a.id_str for a in addresses], ['100', '200'])

    def test_repeated_calls_when_true_total_equals_page_size_do_not_refetch(self):
        """The follow-up query can itself return exactly PAGE_SIZE nodes when that

        happens to be the real total; the cached-fetch flag must stop a second
        call from re-triggering it.
        """
        page_size = GraphQLTemplate.CUSTOMER_ADDRESSES_PAGE_SIZE
        customer = self._gql().Customer.set(
            id='gid://shopify/Customer/5',
            addressesV2={'nodes': [self._address(i) for i in range(page_size)]},
        )

        follow_up_exactly_page_size = {'data': {'customer': {'addressesV2': {
            'nodes': [self._address(100 + i) for i in range(page_size)],
            'pageInfo': {'endCursor': None, 'hasNextPage': False},
        }}}}

        with patch.object(Customer, 'execute', return_value=follow_up_exactly_page_size) as execute_mock:
            first_call = customer.get_addresses()
            second_call = customer.get_addresses()

        execute_mock.assert_called_once()
        self.assertEqual(len(first_call), page_size)
        self.assertEqual([a.id_str for a in first_call], [a.id_str for a in second_call])
