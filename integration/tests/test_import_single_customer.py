# See LICENSE file for full copyright and licensing details.

from copy import deepcopy
from unittest.mock import MagicMock, patch

from odoo.tests import tagged

from .config.integration_init import OdooIntegrationInit


@tagged('post_install', '-at_install', 'test_import_single_customer')
class TestImportSingleCustomer(OdooIntegrationInit):

    def _import_customer(self, customer, addresses):
        integration = self.integration_no_api_1
        Factory = self.env['integration.res.partner.factory']
        domain = [('integration_id', '=', integration.id)]
        previous_factories = Factory.search(domain)
        original_data = deepcopy((customer, addresses))
        adapter = MagicMock(spec=['get_customer_and_addresses'])
        adapter.get_customer_and_addresses.return_value = (customer, addresses)

        with patch.object(type(integration), '_build_adapter', return_value=adapter):
            imported_contacts = integration.import_single_customer(customer['id'])

        adapter.get_customer_and_addresses.assert_called_once_with(customer['id'])
        self.assertEqual((customer, addresses), original_data)
        factories = Factory.search(domain) - previous_factories
        self.assertEqual(len(factories), 1)
        return imported_contacts, factories

    def test_addresses_with_different_companies_keep_primary_mapping(self):
        integration = self.integration_no_api_1
        Partner = self.env['res.partner']

        for address_type in ('invoice', 'delivery', 'other'):
            with self.subTest(address_type=address_type):
                customer = {
                    'id': f'customer-with-two-companies-{address_type}',
                    'person_name': 'John Doe',
                    'email': f'john.{address_type}@example.com',
                }
                primary_company_name = f'Primary Company {address_type}'
                secondary_company_name = f'Secondary Company {address_type}'
                address = {
                    'person_name': customer['person_name'],
                    'email': customer['email'],
                    'street': 'Same Street 1',
                }
                addresses = [
                    dict(address, type='invoice', company_name=primary_company_name),
                    dict(address, type='delivery', company_name=primary_company_name),
                    dict(address, type=address_type, company_name=secondary_company_name),
                ]
                first_contacts, _ = self._import_customer(customer, addresses)
                first_partner = Partner.from_external(integration, customer['id'])
                imported_contacts, factory = self._import_customer(customer, addresses)

                primary_company = Partner.search([
                    ('name', '=', primary_company_name),
                    ('is_company', '=', True),
                    ('company_id', '=', integration.company_id.id),
                ])
                secondary_company = Partner.search([
                    ('name', '=', secondary_company_name),
                    ('is_company', '=', True),
                    ('company_id', '=', integration.company_id.id),
                ])
                self.assertEqual(len(primary_company), 1)
                self.assertEqual(len(secondary_company), 1)
                self.assertEqual(Partner.from_external(integration, customer['id']), first_partner)
                self.assertEqual(first_partner.parent_id, primary_company)
                self.assertEqual(Partner.search([
                    ('parent_id', '=', primary_company.id),
                    ('type', '=', 'contact'),
                    ('email', '=', customer['email']),
                ]), first_partner)
                secondary_address = Partner.search([
                    ('parent_id', '=', secondary_company.id),
                    ('name', '=', customer['person_name']),
                ])
                self.assertEqual(len(secondary_address), 1)
                self.assertEqual(secondary_address.type, address_type)
                self.assertEqual(secondary_address.street, 'Same Street 1')
                self.assertIn(secondary_address, imported_contacts)
                self.assertEqual(set(imported_contacts.ids), set(first_contacts.ids))
                self.assertEqual(len(factory.additional_proxies), 1)
                self.assertFalse(factory.additional_proxies.external_id)

    def test_all_billing_and_shipping_addresses_are_imported(self):
        customer = {'id': 'multiple-addresses', 'person_name': 'John Doe', 'email': 'john@example.com'}
        addresses = [
            dict(customer, type=address_type, street=street)
            for address_type, street in (
                ('invoice', 'Billing 1'),
                ('invoice', 'Billing 2'),
                ('delivery', 'Shipping 1'),
                ('delivery', 'Shipping 2'),
                ('delivery', 'Shipping 3'),
                ('other', 'Other 1'),
                ('', 'Untyped 1'),
            )
        ]
        contacts, factory = self._import_customer(customer, addresses)

        self.assertEqual(factory.customer_id.street, 'Billing 1')
        self.assertEqual(len(factory.billing_proxy), 1)
        self.assertEqual(factory.billing_proxy.street, 'Billing 1')
        self.assertEqual(len(factory.shipping_proxy), 1)
        self.assertEqual(factory.shipping_proxy.street, 'Shipping 1')
        self.assertEqual(len(factory.additional_proxies), 5)
        self.assertEqual(set(contacts.mapped('street')), {address['street'] for address in addresses})
        self.assertEqual(set(contacts.mapped('parent_id').ids), {factory.customer_id.id})
        self.assertEqual(contacts.filtered(lambda p: p.street == 'Billing 2').type, 'invoice')
        self.assertEqual(contacts.filtered(lambda p: p.street == 'Shipping 3').type, 'delivery')
        self.assertEqual(contacts.filtered(lambda p: p.street == 'Untyped 1').type, 'other')

    def test_shipping_only_import_keeps_all_addresses(self):
        customer = {'id': 'shipping-only', 'person_name': 'John Doe', 'email': 'john@example.com'}
        addresses = [dict(customer, type='delivery', street=f'Shipping {i}') for i in range(3)]
        contacts, factory = self._import_customer(customer, addresses)

        self.assertEqual(factory.customer_id.street, 'Shipping 0')
        self.assertEqual(factory.billing_proxy.street, 'Shipping 0')
        self.assertEqual(factory.shipping_proxy.street, 'Shipping 0')
        self.assertEqual(len(factory.additional_proxies), 2)
        self.assertEqual(set(contacts.mapped('street')), {'Shipping 0', 'Shipping 1', 'Shipping 2'})

    def test_explicit_invoice_precedes_untyped_addresses(self):
        customer = {'id': 'untyped-addresses', 'person_name': 'John Doe', 'email': 'john@example.com'}
        addresses = [
            dict(customer, street='Untyped 1'),
            dict(customer, type='invoice', street='Billing 1'),
            dict(customer, type=None, street='Untyped 2'),
        ]
        contacts, factory = self._import_customer(customer, addresses)

        self.assertEqual(factory.customer_id.street, 'Billing 1')
        self.assertEqual(factory.billing_proxy.street, 'Billing 1')
        self.assertEqual(len(factory.additional_proxies), 2)
        self.assertEqual(set(factory.additional_proxies.mapped('type')), {'other_address'})
        self.assertEqual(set(contacts.mapped('street')), {'Billing 1', 'Untyped 1', 'Untyped 2'})

    def test_import_without_addresses(self):
        customer = {'id': 'no-addresses', 'person_name': 'John Doe', 'email': 'john@example.com'}
        contacts, factory = self._import_customer(customer, [])

        self.assertEqual(contacts, factory.customer_id)
        self.assertFalse(factory.billing_proxy)
        self.assertFalse(factory.shipping_proxy)
        self.assertFalse(factory.additional_proxies)

    def test_untyped_address_remains_the_billing_fallback(self):
        customer = {'id': 'untyped-only', 'person_name': 'John Doe', 'email': 'john@example.com'}
        contacts, factory = self._import_customer(customer, [
            dict(customer, street='Primary St'),
            dict(customer, street='Additional St'),
        ])

        self.assertEqual(factory.customer_id.street, 'Primary St')
        self.assertEqual(factory.billing_proxy.street, 'Primary St')
        self.assertFalse(factory.shipping_proxy)
        self.assertEqual(factory.additional_proxies.type, 'other_address')
        self.assertEqual(set(contacts.mapped('street')), {'Primary St', 'Additional St'})

    def test_import_with_only_additional_addresses(self):
        customer = {'id': 'additional-only', 'person_name': 'John Doe', 'email': 'john@example.com'}
        contacts, factory = self._import_customer(customer, [
            dict(customer, type='other', street='Additional St 1'),
            dict(customer, type='', street='Additional St 2'),
        ])

        self.assertFalse(factory.billing_proxy)
        self.assertFalse(factory.shipping_proxy)
        self.assertEqual(len(factory.additional_proxies), 2)
        additional = contacts - factory.customer_id
        self.assertEqual(len(additional), 2)
        self.assertEqual(additional.mapped('parent_id'), factory.customer_id)
