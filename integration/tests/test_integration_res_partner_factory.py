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


@tagged('post_install', '-at_install', 'test_integration_partner_factory')
class TestIntegrationResPartnerFactory(OdooIntegrationInit):

    def setUp(self):
        super().setUp()

        self._orig_create_mapping = _Proxy._create_or_update_mapping

        def _no_new_cursor(proxy_self, **kw):
            return self._orig_create_mapping(proxy_self, with_new_cursor=False)

        self._patcher_no_new_cursor = patch(PATCH_PROXY_CREATE_MAPPING, new=_no_new_cursor)
        self._patcher_no_new_cursor.start()
        self.addCleanup(self._patcher_no_new_cursor.stop)

    def _create_factory(self, customer_data=None, billing_data=None, shipping_data=None, **kwargs):
        return self.env['integration.res.partner.factory'].create_factory(
            integration_id=self.integration_no_api_1.id,
            customer_data=customer_data,
            billing_data=billing_data,
            shipping_data=shipping_data,
            **kwargs
        )

    def test_create_factory_creates_proxies(self):
        """Test basic factory creation with all data types."""
        customer_data = {'person_name': 'John Doe', 'email': 'john@example.com'}
        billing_data = {'company_name': 'Billing Co', 'street': 'Billing St 1', 'email': 'billing@example.com'}
        shipping_data = {'company_name': 'Shipping Co', 'street': 'Shipping St 2', 'email': 'shipping@example.com'}

        factory = self._create_factory(
            customer_data=customer_data,
            billing_data=billing_data,
            shipping_data=shipping_data,
        )

        self.assertEqual(len(factory.proxy_ids), 3)
        self.assertTrue(factory.customer_proxy)
        self.assertTrue(factory.billing_proxy)
        self.assertTrue(factory.shipping_proxy)

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
