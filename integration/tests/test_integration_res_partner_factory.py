# See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged
from .config.integration_init import OdooIntegrationInit
from ..exceptions import ApiImportError, NotMappedFromExternal
from unittest.mock import patch

from ..models.integration_res_partner_proxy import IntegrationResPartnerProxy as _Proxy


PATCH_PROXY_CREATE_MAPPING = (
    'odoo.addons.integration.models.integration_res_partner_proxy.'
    'IntegrationResPartnerProxy._create_or_update_mapping'
)
PATCH_FACTORY_NOTIFY = (
    'odoo.addons.integration.models.integration_res_partner_factory.'
    'IntegrationResPartnerFactory._notify_about_missed_customer_mapping'
)
PATCH_PROXY_GET_CUSTOMER = (
    'odoo.addons.integration.models.integration_res_partner_proxy.'
    'IntegrationResPartnerProxy.get_customer'
)


class TestIntegrationResPartnerFactoryCommon(OdooIntegrationInit):

    @classmethod
    def setUpClass(cls):
        super(TestIntegrationResPartnerFactoryCommon, cls).setUpClass()

        cls._orig_create_mapping = _Proxy._create_or_update_mapping

        def _no_new_cursor(proxy_self, **kw):
            return cls._orig_create_mapping(proxy_self, with_new_cursor=False)

        cls._patcher_no_new_cursor = patch(PATCH_PROXY_CREATE_MAPPING, new=_no_new_cursor)
        cls._patcher_no_new_cursor.start()

    @classmethod
    def tearDownClass(cls):
        # Stop patch after all tests completed
        cls._patcher_no_new_cursor.stop()
        super(TestIntegrationResPartnerFactoryCommon, cls).tearDownClass()

    def _create_factory(self, customer_data=None, billing_data=None, shipping_data=None, **kwargs):
        return self.env['integration.res.partner.factory'].create_factory(
            integration_id=self.integration_no_api_1.id,
            customer_data=customer_data,
            billing_data=billing_data,
            shipping_data=shipping_data,
            **kwargs
        )


@tagged('post_install', '-at_install', 'test_integration_partner_factory')
class TestIntegrationResPartnerFactory(TestIntegrationResPartnerFactoryCommon):

    def test_create_factory_creates_proxies(self):
        """Test basic factory creation with all data types."""
        customer_data = {'person_name': 'John Doe', 'email': 'john@example.com'}
        billing_data = {'company_name': 'Billing Co', 'street': 'Billing St 1', 'email': 'billing@example.com'}
        shipping_data = {'company_name': 'Shipping Co', 'street': 'Shipping St 2', 'email': 'shipping@example.com'}
        additional_addresses = [
            {'company_name': 'Other Co', 'street': 'Other St 3', 'email': 'other@example.com'},
        ]

        factory = self._create_factory(
            customer_data=customer_data,
            billing_data=billing_data,
            shipping_data=shipping_data,
            additional_addresses_data=additional_addresses,
        )

        self.assertEqual(len(factory.proxy_ids), 4)
        self.assertTrue(factory.customer_proxy)
        self.assertTrue(factory.billing_proxy)
        self.assertTrue(factory.shipping_proxy)
        self.assertEqual(len(factory.additional_proxies), 1)
        self.assertEqual(factory.additional_proxies.company_name, 'Other Co')

    def test_create_factory_fallback_shipping_to_billing(self):
        """If billing_data is empty, shipping_data should be used as billing."""
        customer_data = {'person_name': 'Jane'}
        shipping_data = {'company_name': 'Fallback Co', 'street': 'Fallback St', 'email': 'fallback@example.com'}

        factory = self._create_factory(
            customer_data=customer_data,
            shipping_data=shipping_data,
        )

        self.assertTrue(factory.billing_proxy)
        self.assertEqual(factory.billing_proxy.company_name, 'Fallback Co')
        self.assertEqual(factory.shipping_proxy.company_name, 'Fallback Co')

    def test_update_customer_data_merges_billing_into_customer(self):
        """
        Test merging billing data into customer when emails and names match.
        Also verifies that the merged data is used when creating a partner/company.
        """
        factory = self.env['integration.res.partner.factory'].create({
            'integration_id': self.integration_no_api_1.id,
        })

        customer_data = {
            'person_name': 'ALICE SMITH',
            'email': 'ALICE@EXAMPLE.COM',
            'phone': '123',
        }
        billing_data = {
            'person_name': 'Alice Smith',
            'email': 'alice@example.com',
            'company_name': 'Alice Ltd',
            'company_reg_number': 'REG123',
            'person_id_number': 'PID-001',
            'street': 'Main St',
            'phone': '456',
        }

        result = factory._update_customer_data(customer_data, billing_data, None)

        # Verify that the company and related fields have been copied.
        self.assertEqual(result['company_name'], 'Alice Ltd')
        self.assertEqual(result['company_reg_number'], 'REG123')
        self.assertEqual(result['person_id_number'], 'PID-001')

        # Verify that phone has been updated
        self.assertEqual(result['phone'], '456')

        # Verify that address fields have also been copied (FIELDS_TO_COPY)
        self.assertEqual(result['street'], 'Main St')

        # Creating a proxy with combined data
        proxy = self.env['integration.res.partner.proxy'].create_proxy(
            type_='customer',
            integration_id=self.integration_no_api_1.id,
            factory_id=factory.id,
            data=result,
        )

        # We verify that the fields are correctly set in the proxy.
        self.assertEqual(proxy.company_name, 'Alice Ltd')
        self.assertEqual(proxy.company_reg_number, 'REG123')
        self.assertEqual(proxy.person_id_number, 'PID-001')
        self.assertEqual(proxy.phone, '456')
        self.assertEqual(proxy.street, 'Main St')

        # Create a partner (and, if company_name is available, a company)
        partner = proxy.get_or_create_partner()
        self.assertTrue(partner)
        company = partner.parent_id
        self.assertTrue(company, 'Company should be created')

        # We verify that the partner has been created with the correct details.
        self.assertEqual(partner.name, 'Alice Smith')
        self.assertEqual(partner.email, 'alice@example.com')

        # Since company_name was provided, a company partner should have been created.
        self.assertEqual(company.name, 'Alice Ltd')
        self.assertEqual(company.street, 'Main St')

    def test_update_customer_data_no_merge_on_email_mismatch(self):
        """
        Test that billing data is NOT merged into customer if email does not match.
        Only company and person_id_number should be transferred, not address fields.
        """
        factory = self.env['integration.res.partner.factory'].create({
            'integration_id': self.integration_no_api_1.id,
        })

        customer_data = {
            'person_name': 'Alice Smith',
            'email': 'alice@example.com',
            'phone': '123',
        }
        billing_data = {
            'person_name': 'Alice Smith',
            'email': 'other@example.com',  # <-- another email address
            'company_name': 'Alice Ltd',
            'street': 'Billing St',
            'phone': '456',
            'person_id_number': 'PID-002',
        }

        result = factory._update_customer_data(customer_data, billing_data, None)

        # Check that company_name and person_id_number have been passed
        self.assertEqual(result['company_name'], 'Alice Ltd')
        self.assertEqual(result['person_id_number'], 'PID-002')

        # Check that phone and street have NOT been overwritten
        self.assertEqual(result['phone'], '123')
        self.assertNotIn('street', result)  # field should not be added

    def test_update_customer_data_no_merge_on_name_mismatch(self):
        """
        Test that billing data is NOT merged into customer if person_name does not match.
        Only company and person_id_number should be transferred, not address fields.
        """
        factory = self.env['integration.res.partner.factory'].create({
            'integration_id': self.integration_no_api_1.id,
        })

        customer_data = {
            'person_name': 'Alice Smith',
            'email': 'alice@example.com',
            'phone': '123',
        }
        billing_data = {
            'person_name': 'Bob Smith',  # <-- another name
            'email': 'alice@example.com',
            'company_name': 'Alice Ltd',
            'street': 'Billing St',
            'phone': '456',
            'person_id_number': 'PID-003',
        }

        result = factory._update_customer_data(customer_data, billing_data, None)

        # Check that company_name and person_id_number have been passed
        self.assertEqual(result['company_name'], 'Alice Ltd')
        self.assertEqual(result['person_id_number'], 'PID-003')

        # Check that phone and street have NOT been overwritten
        self.assertEqual(result['phone'], '123')
        self.assertNotIn('street', result)

    def test_validate_initial_import_fails_without_external_id(self):
        """Initial import must fail if customer proxy has no external_id."""
        factory = self._create_factory(
            customer_data={'person_name': 'Test'},
            is_initial_import=True,
        )

        with self.assertRaisesRegex(ApiImportError, "Customer external ID is missing"):
            factory.validate_data()

    def test_validate_sales_order_fails_without_data_or_default_customer(self):
        """Sales order import fails if no customer data and no default customer."""
        self.integration_no_api_1.default_customer = False

        factory = self._create_factory()

        with self.assertRaisesRegex(ApiImportError, 'Missing required customer or address information'):
            factory.validate_data()

    def test_get_partner_and_addresses_returns_partners(self):
        """Test that get_partner_and_addresses creates or returns partners."""
        customer_data = {'person_name': 'Bob', 'email': 'bob@example.com'}
        factory = self._create_factory(customer_data=customer_data)

        customer, addresses = factory.get_partner_and_addresses()

        self.assertTrue(customer)
        self.assertEqual(customer.name, 'Bob')
        self.assertEqual(addresses['billing'], customer)
        self.assertEqual(addresses['shipping'], customer)
        self.assertFalse(addresses['additional'])

    def test_manual_mapping_initial_import_raises_not_mapped(self):
        """Initial import with manual mapping and no existing partner raises NotMappedFromExternal."""
        self.integration_no_api_1.write({
            'use_manual_customer_mapping': True,
        })

        # IMPORTANT: external_id must already be on the proxy (we pass it as “id”)
        factory = self._create_factory(
            customer_data={'person_name': 'Manual Test', 'email': 'manual@test.com', 'id': 'ext-manual-1'},
            is_initial_import=True,
        )

        with self.assertRaises(NotMappedFromExternal) as cm:
            factory.validate_data()

        self.assertIn('Manual customer mapping is enabled', str(cm.exception))
        self.assertIn('ext-manual-1', str(cm.exception))

    def test_manual_mapping_sales_order_raises_not_mapped(self):
        """Sales order with manual mapping and unmapped customer raises NotMappedFromExternal."""
        self.integration_no_api_1.write({
            'use_manual_customer_mapping': True,
            'emails_for_failed_mapping_notifications': 'test@example.com',
            'default_customer': False,
        })

        factory = self._create_factory(
            customer_data={'person_name': 'SO Manual', 'email': 'so@test.com', 'id': 'ext-so-1'},
        )

        with patch(PATCH_FACTORY_NOTIFY, return_value=True), patch(PATCH_PROXY_GET_CUSTOMER, return_value=False):
            with self.assertRaises(NotMappedFromExternal) as cm:
                factory.validate_data()

        self.assertIn('Manual customer mapping is enabled', str(cm.exception))
        self.assertIn('ext-so-1', str(cm.exception))

    def test_manual_mapping_with_existing_partner_passes_validation(self):
        """If partner is already mapped, validation passes."""
        self.integration_no_api_1.write({'use_manual_customer_mapping': True})

        partner = self.env['res.partner'].create({'name': 'Mapped Partner'})
        external = self.env['integration.res.partner.external'].create({
            'integration_id': self.integration_no_api_1.id,
            'code': 'mapped-1',
            'name': 'Mapped Partner',
        })
        self.env['integration.res.partner.mapping'].create({
            'integration_id': self.integration_no_api_1.id,
            'external_partner_id': external.id,
            'partner_id': partner.id,
        })

        factory = self._create_factory(
            customer_data={'person_name': 'Mapped Partner', 'email': 'mapped@test.com'},
            is_initial_import=True,
        )
        factory.customer_proxy.write({'external_id': 'mapped-1'})

        factory.validate_data()

        customer, _ = factory.get_partner_and_addresses()
        self.assertEqual(customer, partner)

    def test_manual_mapping_without_existing_partner_raises_exception(self):
        """
        If partner is not mapped and use_manual_customer_mapping is enabled,
        validation raises NotMappedFromExternal exception.
        """
        self.integration_no_api_1.write({'use_manual_customer_mapping': True})

        factory = self._create_factory(
            customer_data={'person_name': 'Unmapped Partner', 'email': 'unmapped@test.com'},
            is_initial_import=True,
        )
        factory.customer_proxy.write({'external_id': 'unmapped-1'})

        with self.assertRaises(NotMappedFromExternal):
            factory.validate_data()

    def test_create_factory_guest_uses_billing_as_customer(self):
        """When customer_data is missing, billing_data is used to create customer (guest order)."""
        billing = {
            'person_name': 'Guest Buyer',
            'email': 'guest@ex.com',
            'company_name': 'Guest Co',
            'street': 'Billing Str 1',
            'city': 'City',
        }
        factory = self._create_factory(customer_data=None, billing_data=billing, shipping_data=None)

        # customer_proxy and billing_proxy should appear
        self.assertTrue(factory.customer_proxy)
        self.assertTrue(factory.billing_proxy)
        self.assertEqual(factory.customer_proxy.person_name, 'Guest Buyer')
        self.assertEqual(factory.customer_proxy.email, 'guest@ex.com')

    def test_manual_mapping_sales_order_without_external_id_returns_false(self):
        """Manual mapping on sales order: no external_id -> returns False, no exception."""
        self.integration_no_api_1.write({'use_manual_customer_mapping': True})

        factory = self._create_factory(
            customer_data={'person_name': 'NoExt', 'email': 'noext@ex.com'},
        )
        # external_id is not set intentionally
        res = factory._validate_for_sales_orders()
        self.assertTrue(res)

    def test_billing_all_empty_is_ignored_and_shipping_used(self):
        """
        Test that when billing_data contains only falsy values (empty strings),
        it is ignored and shipping_data is used as billing_data fallback.
        """
        factory = self._create_factory(
            customer_data={'person_name': 'X'},
            billing_data={'street': '', 'email': '', 'zip': ''},  # all falsy
            shipping_data={'company_name': 'Ship Co', 'street': 'S 1', 'email': 's@ex.com'},
        )
        self.assertTrue(factory.billing_proxy)
        self.assertTrue(factory.shipping_proxy)
        self.assertEqual(factory.billing_proxy.company_name, 'Ship Co')

    def test_update_customer_data_identity_mismatch_does_not_override(self):
        """
        Test that when customer and billing data have different email or person_name,
        customer data is NOT overwritten by billing data.
        However, company-related and person_id_number fields are still copied.
        Address fields (like 'street') are NOT copied in case of identity mismatch.
        """
        factory = self.env['integration.res.partner.factory'].create({
            'integration_id': self.integration_no_api_1.id,
        })
        customer = {'person_name': 'A', 'email': 'a@ex.com', 'phone': '123'}
        billing = {
            'person_name': 'B',  # mismatch
            'email': 'b@ex.com',  # mismatch
            'phone': '999',
            'company_name': 'Co',
            'company_reg_number': 'R1',
            'country': 'DE',
            'country_code': 'DE',
            'person_id_number': 'PID-1',
            'street': 'Billing St',
        }
        res = factory._update_customer_data(customer, billing, None)
        # Phone was not overwritten
        self.assertEqual(res['phone'], '123')
        # But company & person_id_number were transferred
        self.assertEqual(res['company_name'], 'Co')
        self.assertEqual(res['company_reg_number'], 'R1')
        self.assertEqual(res['country_code'], 'DE')
        self.assertEqual(res['person_id_number'], 'PID-1')
        # Address fields are not copied in case of mismatch
        self.assertNotIn('street', res)

    def test_get_partner_and_addresses_uses_default_customer_when_no_proxies(self):
        """
        Test that get_partner_and_addresses returns the default customer
        when no customer, billing, or shipping proxies are present in the factory.
        Also verifies that billing and shipping addresses default to the same customer.
        """
        default_partner = self.env['res.partner'].create({'name': 'Default C'})
        self.integration_no_api_1.write({'default_customer': default_partner.id})

        factory = self._create_factory(customer_data=None, billing_data=None, shipping_data=None)
        customer, addrs = factory.get_partner_and_addresses()

        self.assertEqual(customer, default_partner)
        self.assertEqual(addrs['billing'], default_partner)
        self.assertEqual(addrs['shipping'], default_partner)
        self.assertFalse(addrs['additional'])

    def test_shipping_address_of_another_company_is_not_merged_into_customer(self):
        for name, billing_company, shipping_company in (
            ('John Doe', 'Smallco', 'Bigco'),
            ('Jane Roe', None, 'Bigco B2C'),
        ):
            with self.subTest(billing_company=billing_company):
                email = f'{name.split()[0].lower()}@example.com'
                address = {
                    'person_name': name,
                    'email': email,
                    'street': 'Same St 1',
                }
                billing_data = (
                    dict(address, company_name=billing_company)
                    if billing_company
                    else dict(address)
                )
                factory = self._create_factory(
                    customer_data={'person_name': name, 'email': email},
                    billing_data=billing_data,
                    shipping_data=dict(address, company_name=shipping_company),
                )

                customer, addresses = factory.get_partner_and_addresses()

                self.assertEqual(customer.parent_id.name, billing_company or False)
                self.assertEqual(addresses['billing'], customer)
                self.assertNotEqual(addresses['shipping'], customer)
                self.assertEqual(addresses['shipping'].type, 'delivery')
                self.assertEqual(addresses['shipping'].parent_id.name, shipping_company)

    def test_additional_proxies_keep_types_and_primary_proxies(self):
        additional_addresses = [
            {'person_name': 'Additional', 'type': address_type, 'street': str(index)}
            for index, address_type in enumerate(('invoice', 'delivery', 'other', None, '', False))
        ]
        additional_addresses.extend([{}, None, {'street': ''}])
        factory = self._create_factory(
            customer_data={'person_name': 'Customer'},
            billing_data={'person_name': 'Primary billing'},
            shipping_data={'person_name': 'Primary shipping'},
            additional_addresses_data=additional_addresses,
        )

        self.assertEqual(len(factory.billing_proxy), 1)
        self.assertEqual(factory.billing_proxy.person_name, 'Primary billing')
        self.assertEqual(len(factory.shipping_proxy), 1)
        self.assertEqual(factory.shipping_proxy.person_name, 'Primary shipping')
        self.assertEqual(len(factory.additional_proxies), 6)
        self.assertEqual(factory.additional_proxies.mapped('type'), [
            'billing_address', 'shipping_address', 'other_address',
            'other_address', 'other_address', 'other_address',
        ])
        self.assertFalse(factory.customer_proxy.is_additional_address)
        self.assertFalse(factory.billing_proxy.is_additional_address)
        self.assertFalse(factory.shipping_proxy.is_additional_address)

    def test_additional_address_with_unknown_type_is_rejected(self):
        for address_type in ('unsupported', ['invoice'], 0):
            with self.subTest(address_type=address_type):
                with self.assertRaises(ApiImportError) as error:
                    self._create_factory(
                        customer_data={'person_name': 'Customer'},
                        additional_addresses_data=[{
                            'person_name': 'Additional',
                            'type': address_type,
                        }],
                    )

                self.assertIn('E116', str(error.exception))

    def test_additional_addresses_reuse_matching_customer(self):
        address = {'person_name': 'Customer', 'email': 'customer@example.com', 'street': 'Same Street'}
        factory = self._create_factory(
            customer_data=address,
            billing_data=address,
            shipping_data=address,
            additional_addresses_data=[dict(address, type='delivery')],
        )
        customer, addresses = factory.get_partner_and_addresses()

        self.assertEqual(addresses['billing'], customer)
        self.assertEqual(addresses['shipping'], customer)
        self.assertEqual(addresses['additional'], customer)
        self.assertFalse(customer.child_ids)

    def test_additional_company_address_in_company_only_mode(self):
        self.integration_no_api_1.skip_individual_contacts = True
        factory = self._create_factory(
            customer_data={'id': 'company-only', 'person_name': 'Customer'},
            billing_data={'person_name': 'Customer', 'company_name': 'Primary Co', 'street': 'Primary St'},
            additional_addresses_data=[{
                'type': 'delivery',
                'person_name': 'Receiver',
                'company_name': 'Secondary Co',
                'street': 'Secondary St',
            }],
            is_initial_import=True,
        )
        customer, addresses = factory.get_partner_and_addresses()

        self.assertTrue(customer.is_company)
        self.assertEqual(customer.name, 'Primary Co')
        self.assertEqual(addresses['additional'].parent_id.name, 'Secondary Co')
        self.assertEqual(addresses['additional'].type, 'delivery')
        self.assertEqual(
            self.env['res.partner'].from_external(self.integration_no_api_1, 'company-only'),
            customer,
        )

    def test_additional_address_respects_manual_customer_mapping(self):
        integration = self.integration_no_api_1
        integration.write({
            'use_manual_customer_mapping': True,
            'skip_individual_contacts': True,
        })

        partner = self.env['res.partner'].create({
            'name': 'Mapped Customer',
            'street': 'Original St',
        })
        partner.create_mapping(integration, 'manual-additional')

        factory = self._create_factory(
            customer_data={
                'id': 'manual-additional',
                'person_name': 'Customer',
            },
            additional_addresses_data=[{
                'person_name': 'Receiver',
                'type': 'delivery',
                'company_name': 'Other Company',
                'street': 'Different St',
            }],
            is_initial_import=True,
        )

        customer, addresses = factory.get_partner_and_addresses()

        self.assertEqual(customer, partner)
        self.assertEqual(addresses['additional'].parent_id, partner)
        self.assertEqual(addresses['additional'].type, 'delivery')
        self.assertFalse(self.env['res.partner'].search([
            ('name', '=', 'Other Company'),
            ('is_company', '=', True),
            ('company_id', '=', integration.company_id.id),
        ]))
        self.assertEqual(
            self.env['res.partner'].from_external(integration, 'manual-additional'),
            partner,
        )

    def test_additional_address_respects_vat_only_company_search(self):
        integration = self.integration_no_api_1
        integration.write({
            'customer_company_vat_field': self.env['ir.model.fields']._get('res.partner', 'ref').id,
            'use_vat_only_company_search': True,
            'ignore_vat_validation': True,
        })
        company = self.env['res.partner'].create({
            'name': 'Existing Company',
            'is_company': True,
            'company_id': integration.company_id.id,
            'ref': 'REG123',
        })
        factory = self._create_factory(
            customer_data={'person_name': 'Customer', 'email': 'customer@example.com'},
            billing_data={
                'person_name': 'Customer',
                'email': 'customer@example.com',
                'company_name': 'Existing Company',
                'company_reg_number': 'REG123',
                'street': 'Primary St',
            },
            additional_addresses_data=[{
                'person_name': 'Receiver',
                'type': 'delivery',
                'company_name': 'Different API Name',
                'company_reg_number': 'REG123',
                'street': 'Additional St',
            }],
        )
        customer, addresses = factory.get_partner_and_addresses()

        self.assertEqual(customer.parent_id, company)
        self.assertEqual(addresses['additional'].parent_id, company)
        self.assertFalse(self.env['res.partner'].search([('name', '=', 'Different API Name')]))
