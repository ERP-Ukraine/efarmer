# See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from odoo import models
from odoo.tests import tagged
from .config.integration_init import OdooIntegrationInit, load_xml


@tagged('post_install', '-at_install', 'test_integration_partner_proxy')
class TestIntegrationResPartnerProxy(OdooIntegrationInit):

    @classmethod
    def setUpClass(cls):
        super(TestIntegrationResPartnerProxy, cls).setUpClass()
        # Load base integration XML data first (needed for refs)
        load_xml(
            cls.env,
            module='integration',
            path_file='tests/data',
            filename='init_sale_integration.xml',
        )
        integration_no_api_1 = cls.env.ref('integration.integration_no_api_1')
        cls.factory = cls.env['integration.res.partner.factory'].create({
            'integration_id': integration_no_api_1.id,
        })

    def _create_proxy(self, type_: str, data: dict) -> models.Model:
        """
        Helper method to create a proxy with consistent parameters.
        """
        return self.env['integration.res.partner.proxy'].create_proxy(
            type_=type_,
            integration_id=self.integration_no_api_1.id,
            factory_id=self.factory.id,
            data=data,
        )

    def test_create_proxy_with_empty_data(self):
        """Test that proxy is not created when data is empty."""
        proxy = self._create_proxy('customer', {})
        self.assertFalse(proxy)

    def test_create_proxy_with_none_data(self):
        """Test that proxy is not created when data is None."""
        with self.assertRaises(ValueError):
            self._create_proxy('customer', None)

    def test_create_proxy_with_invalid_type(self):
        """Test that ValueError is raised for invalid proxy type."""
        data = {'person_name': 'Test'}
        with self.assertRaises(ValueError):
            self._create_proxy('invalid_type', data)

    def test_create_customer_proxy_with_minimal_data(self):
        """Test creating customer proxy with only required fields."""
        data = {
            'person_name': 'John Doe',
            'email': 'john@example.com',
            'phone': '+1234567890',
        }

        proxy = self._create_proxy('customer', data)

        self.assertTrue(proxy)
        self.assertEqual(proxy.type, 'customer')
        self.assertEqual(proxy.person_name, 'John Doe')
        self.assertEqual(proxy.email, 'john@example.com')
        self.assertEqual(proxy.phone, '+1234567890')

    def test_create_customer_proxy_without_required_fields(self):
        """Test that proxy is not created when both person_name and email are missing."""
        data = {
            'phone': '+1234567890',
            'street': 'Main St',
        }

        proxy = self._create_proxy('customer', data)
        self.assertFalse(proxy)

    def test_create_customer_proxy_with_only_email(self):
        """Test creating proxy with only email (name missing)."""
        data = {
            'email': 'jane@example.com',
        }

        proxy = self._create_proxy('customer', data)

        self.assertTrue(proxy)
        self.assertEqual(proxy.email, 'jane@example.com')

    def test_create_customer_proxy_with_only_person_name(self):
        """Test creating proxy with only person_name (email missing)."""
        data = {
            'person_name': 'Jane Doe',
        }

        proxy = self._create_proxy('customer', data)

        self.assertTrue(proxy)
        self.assertEqual(proxy.person_name, 'Jane Doe')

    def test_normalize_email_in_proxy(self):
        """Test that email is normalized during proxy creation."""
        data = {
            'person_name': 'Bob Smith',
            'email': 'BOB.SMITH@EXAMPLE.COM',
        }

        proxy = self._create_proxy('customer', data)

        self.assertTrue(proxy)
        self.assertEqual(proxy.email, 'bob.smith@example.com')

    def test_proxy_phone_format_with_country_code_uses_formatter(self):
        """If there is a country_code -> _phone_format is used; the result is returned as is."""
        data = {
            'person_name': 'Phone ES',
            'email': 'p@es.es',
            'phone': '691234044',
            'country_code': 'ES',
        }
        proxy = self._create_proxy('customer', data)
        self.assertTrue(proxy)

        # Mock the internal formatter of the model to avoid dependency on phonenumbers.
        with patch.object(type(proxy), "_phone_format", return_value="+34691234044"):
            res = proxy._proxy_phone_format(
                integration_id=self.integration_no_api_1.id,
                phone_number='691234044',
                data=data,
            )
        self.assertEqual(res, "+34691234044")

    def test_proxy_phone_format_without_country_returns_original(self):
        """If the country is not resolved (no country/country_code) -> return the original value."""
        data = {
            'person_name': 'No Country',
            'email': 'nocountry@test.com',
            'phone': '0176 1234567',
        }
        proxy = self._create_proxy('customer', data)
        self.assertTrue(proxy)

        # Even if _phone_format suddenly returns something, the method will not reach it without the country
        res = proxy._proxy_phone_format(
            integration_id=self.integration_no_api_1.id,
            phone_number='0176 1234567',
            data=data,
        )
        self.assertEqual(res, '0176 1234567')

    def test_proxy_phone_format_when_formatter_fails_falls_back(self):
        """If the internal formatter returns False (e.g., no phonenumbers) -> return the original number."""
        data = {
            'person_name': 'Fallback',
            'email': 'fallback@test.com',
            'phone': '691234044',
            'country_code': 'ES',
        }
        proxy = self._create_proxy('customer', data)
        self.assertTrue(proxy)

        with patch.object(type(proxy), "_phone_format", return_value=False):
            res = proxy._proxy_phone_format(
                integration_id=self.integration_no_api_1.id,
                phone_number='691234044',
                data=data,
            )
        self.assertEqual(res, '691234044')

    def test_format_phone_without_country(self):
        """Test phone formatting when country is missing."""
        data = {
            'person_name': 'Phone Test',
            'email': 'phone@test.com',
            'phone': '+15551234567',
        }
        proxy = self._create_proxy('customer', data)
        self.assertEqual(proxy.phone, '+15551234567')  # Should pass through unchanged

    def test_create_billing_address_proxy(self):
        """Test creating billing address proxy."""
        data = {
            'person_name': 'Charlie Brown',
            'email': 'charlie@example.com',
            'street': 'Maple Ave',
            'city': 'Berlin',
            'country_code': 'DE',
        }

        proxy = self._create_proxy('billing_address', data)

        self.assertTrue(proxy)
        self.assertEqual(proxy.type, 'billing_address')
        self.assertEqual(proxy.city, 'Berlin')
        self.assertEqual(proxy.country_code, 'DE')

    def test_create_shipping_address_proxy(self):
        """Test creating shipping address proxy."""
        data = {
            'person_name': 'Diana Prince',
            'mobile': '+4915712345678',
            'zip': '10115',
        }

        proxy = self._create_proxy('shipping_address', data)

        self.assertTrue(proxy)
        self.assertEqual(proxy.type, 'shipping_address')
        self.assertIn('+49', proxy.mobile)

    def test_external_id_set_for_customer_type(self):
        """Test that external_id is set from data['id'] for customer type."""
        data = {
            'person_name': 'Eve Clark',
            'email': 'eve@example.com',
            'id': 'ext-12345',
        }

        proxy = self._create_proxy('customer', data)

        self.assertTrue(proxy)
        self.assertEqual(proxy.external_id, 'ext-12345')

    def test_company_name_and_reg_number_preserved(self):
        """Test that company-specific fields are preserved."""
        data = {
            'person_name': 'Frank Wilson',
            'email': 'frank@example.com',
            'company_name': 'Acme Corp',
            'company_reg_number': 'DE276452187',
        }

        proxy = self._create_proxy('customer', data)

        self.assertTrue(proxy)
        self.assertEqual(proxy.company_name, 'Acme Corp')
        self.assertEqual(proxy.company_reg_number, 'DE276452187')

    def test_empty_string_values_are_stripped_to_empty(self):
        """Test that empty strings are converted to empty values."""
        data = {
            'person_name': '   ',
            'email': '',
            'phone': '\t\n',
        }

        proxy = self._create_proxy('customer', data)
        self.assertFalse(proxy)

    def test_non_string_values_preserved(self):
        """Test that non-string values are passed through unchanged."""
        data = {
            'person_name': 'Grace Lee',
            'email': 'grace@example.com',
            'pricelist_id': 42,
            'other': None,
        }

        proxy = self._create_proxy('customer', data)

        self.assertTrue(proxy)
        self.assertEqual(proxy.pricelist_id, '42')
        self.assertIs(proxy.other, False)  # TransientModel converts None to False

    def test_integration_id_available_via_related_field(self):
        """Test that integration_id is available via factory relation."""
        data = {
            'person_name': 'Henry Ford',
            'email': 'henry@example.com',
        }

        proxy = self._create_proxy('customer', data)

        self.assertTrue(proxy)
        self.assertEqual(proxy.integration_id.id, self.integration_no_api_1.id)

    def test_get_integration_tag_creates_and_reuses_tag(self):
        """Test that _get_integration_tag creates tag under main tag and reuses it."""
        ResPartnerTag = self.env['res.partner.category']
        integration_name = self.integration_no_api_1.name

        proxy = self._create_proxy('customer', {
            'person_name': 'Tag Test',
            'email': 'tag@test.com',
        })

        # First call — creates the tag
        tag1 = proxy._get_integration_tag()
        self.assertEqual(tag1.name, integration_name)
        self.assertEqual(tag1.parent_id, self.env.ref('integration.main_integration_tag'))

        # Second call — returns the same tag
        tag2 = proxy._get_integration_tag()
        self.assertEqual(tag1, tag2)

        # Ensure that exactly one tag was created
        tags = ResPartnerTag.search([
            ('name', '=', integration_name),
            ('parent_id', '=', self.env.ref('integration.main_integration_tag').id),
        ])
        self.assertEqual(len(tags), 1)

    def test_get_or_create_company_with_vat_validation_disabled(self):
        """Test company creation when VAT validation is disabled."""
        self.integration_no_api_1.write({'ignore_vat_validation': True})
        vat_field = self.env.ref('base.field_res_partner__vat')
        self.integration_no_api_1.customer_company_vat_field = vat_field

        data = {
            'person_name': 'VAT Disabled',
            'email': 'vat.disabled@example.com',
            'company_name': 'VAT Disabled Corp',
            'company_reg_number': 'INVALIDVAT123',
        }
        proxy = self._create_proxy('customer', data)
        company = proxy._get_or_create_company()

        self.assertTrue(company)
        self.assertEqual(company.vat, 'INVALIDVAT123')

    def test_collect_company_search_domain_vat_only_adds_company_id(self):
        """
        use_vat_only_company_search=True
        The domain must be built only on VAT and MUST contain a restriction on company_id
        """
        # Configure which field to use as VAT
        vat_field = self.env.ref('base.field_res_partner__vat')
        self.integration_no_api_1.write({
            'customer_company_vat_field': vat_field.id,
            'use_vat_only_company_search': True,
        })

        data = {
            'person_name': 'VAT Only',
            'email': 'v@t.es',
            'company_name': 'Some Co',
            'company_reg_number': 'ESB12345678',
        }
        proxy = self._create_proxy('customer', data)
        self.assertTrue(proxy)

        company_vals = proxy._prepare_company_vals()
        domain = proxy._collect_company_search_domain(company_vals)

        # is_company is present
        self.assertIn(('is_company', '=', True), domain)

        # company_id is present
        has_company_id = any(
            item[0] == 'company_id' and item[1] == 'in' for item in domain
        )
        self.assertTrue(has_company_id, "The domain does not contain company_id 'in' when searching only by VAT")

        # VAT is present
        self.assertIn((vat_field.name, '=', 'ESB12345678'), domain)

    def test_collect_company_search_domain_vat_appended_when_not_only(self):
        """
        use_vat_only_company_search=False
        VAT is added as one of the criteria,but the domain must still include company_id 'in'
        """
        vat_field = self.env.ref('base.field_res_partner__vat')
        self.integration_no_api_1.write({
            'customer_company_vat_field': vat_field.id,
            'use_vat_only_company_search': False,
        })

        data = {
            'person_name': 'VAT Appended',
            'email': 'v@t.es',
            'company_name': 'Some Co',
            'company_reg_number': 'ESX9999999',
        }
        proxy = self._create_proxy('customer', data)
        self.assertTrue(proxy)

        company_vals = proxy._prepare_company_vals()
        domain = proxy._collect_company_search_domain(company_vals)

        # VAT is present
        self.assertIn((vat_field.name, '=', 'ESX9999999'), domain)

        # company_id is present
        has_company_id = any(
            item[0] == 'company_id' and item[1] == 'in' for item in domain
        )
        self.assertTrue(has_company_id, "The domain must contain company_id 'in'")

        # is_company is present
        self.assertIn(('is_company', '=', True), domain)

    def test_collect_company_search_domain_without_vat_field_uses_defaults(self):
        """
        If the VAT field is not configured or there is no VAT value in company_vals,
        the method should use the default criteria (but still include company_id).
        """
        # Reset VAT settings
        self.integration_no_api_1.write({
            'customer_company_vat_field': False,
            'use_vat_only_company_search': False,
        })

        data = {
            'person_name': 'No VAT',
            'email': 'novat@test.com',
            'company_name': 'No VAT Co',
        }
        proxy = self._create_proxy('customer', data)
        self.assertTrue(proxy)

        company_vals = proxy._prepare_company_vals()
        domain = proxy._collect_company_search_domain(company_vals)

        # company_id is present (integration must be limited to its own company)
        has_company_id = any(
            item[0] == 'company_id' and item[1] == 'in' for item in domain
        )
        self.assertTrue(has_company_id, "Even without VAT, the domain must include company_id 'in'")

        # is_company is present
        self.assertIn(('is_company', '=', True), domain)

    def test_search_domain_with_personal_id_field(self):
        """Test that personal ID field is included in search domain."""
        person_id_field = self.env.ref('base.field_res_partner__ref')
        self.integration_no_api_1.customer_personal_id_field = person_id_field

        proxy = self._create_proxy('customer', {
            'person_name': 'ID Test',
            'email': 'id@test.com',
            'person_id_number': 'P123456',
        })

        partner_vals = {'name': 'John'}
        domain = proxy._collect_partner_search_domain(partner_vals)

        self.assertIn(('ref', '=', 'P123456'), domain)

    def test_mapping_compatibility_with_company_parent_mismatch(self):
        """Test that mapped partner with different parent company is rejected."""
        # Parent company in company_id_1
        parent_company_1 = self.env['res.partner'].create({
            'name': 'Company 1',
            'is_company': True,
            'company_id': self.company_id_1.id,
        })

        contact = self.env['res.partner'].create({
            'name': 'Mapped Contact',
            'company_id': self.company_id_1.id,
            'is_company': False,
            'parent_id': parent_company_1.id,
        })
        external_contact = self.env['integration.res.partner.external'].create({
            'integration_id': self.integration_no_api_1.id,
            'code': '123',
            'name': contact.name,
        })
        self.env['integration.res.partner.mapping'].create({
            'integration_id': self.integration_no_api_1.id,
            'external_partner_id': external_contact.id,
            'partner_id': contact.id,
        })

        # The context requests Company 2 to have _get_or_create_company() return another company.
        proxy = self._create_proxy('customer', {
            'person_name': 'Contact',
            'email': 'contact@test.com',
            'company_name': 'Company 2',
            'external_id': 'ext-999',
        })

        compatible = proxy._is_mapping_compatible(contact)
        self.assertFalse(compatible)

    def test_mapping_compatibility_with_parent_match(self):
        """Mapped contact with matching parent company is accepted."""
        parent_company_1 = self.env['res.partner'].create({
            'name': 'Company 1',
            'is_company': True,
            'company_id': self.company_id_1.id,
        })
        contact = self.env['res.partner'].create({
            'name': 'Mapped Contact',
            'is_company': False,
            'company_id': self.company_id_1.id,
            'parent_id': parent_company_1.id,
        })
        ext = self.env['integration.res.partner.external'].create({
            'integration_id': self.integration_no_api_1.id,
            'code': 'c-1',
            'name': contact.name,
        })
        self.env['integration.res.partner.mapping'].create({
            'integration_id': self.integration_no_api_1.id,
            'external_partner_id': ext.id,
            'partner_id': contact.id,
        })

        proxy = self._create_proxy('customer', {
            'person_name': 'Contact',
            'email': 'contact@test.com',
            'company_name': 'Company 1',
        })
        self.assertTrue(proxy._is_mapping_compatible(contact))

    def test_mapping_compatibility_rejects_on_company_id_guard(self):
        """mapped_partner.company_id != integration.company_id -> reject (early guard)."""
        contact = self.env['res.partner'].create({
            'name': 'Foreign Contact',
            'is_company': False,
            'company_id': self.company_id_2.id,
        })
        ext = self.env['integration.res.partner.external'].create({
            'integration_id': self.integration_no_api_1.id,
            'code': 'c-2',
            'name': contact.name,
        })
        self.env['integration.res.partner.mapping'].create({
            'integration_id': self.integration_no_api_1.id,
            'external_partner_id': ext.id,
            'partner_id': contact.id,
        })

        proxy = self._create_proxy('customer', {
            'person_name': 'X',
            'email': 'x@test.com',
            'company_name': 'Company 1',
        })
        self.assertFalse(proxy._is_mapping_compatible(contact))

    def test_mapping_compatibility_company_only_wrong_company_rejects(self):
        """skip_individual=True; mapped company != expected company -> reject."""
        mapped_company = self.env['res.partner'].create({
            'name': 'Other Co',
            'is_company': True,
            'company_id': self.company_id_1.id,
        })
        ext = self.env['integration.res.partner.external'].create({
            'integration_id': self.integration_no_api_1.id,
            'code': 'co-1',
            'name': mapped_company.name,
        })
        self.env['integration.res.partner.mapping'].create({
            'integration_id': self.integration_no_api_1.id,
            'external_partner_id': ext.id,
            'partner_id': mapped_company.id,
        })

        proxy = self._create_proxy('customer', {
            'person_name': 'Y',
            'email': 'y@test.com',
            'company_name': 'Company 1',
        })
        self.integration_no_api_1.write({'skip_individual_contacts': True})
        self.assertFalse(proxy._is_mapping_compatible(mapped_company))

    def test_mapping_compatibility_company_only_exact_company_accepts(self):
        """skip_individual=True; mapped company == expected company -> accept."""
        mapped_company = self.env['res.partner'].create({
            'name': 'Company 1',
            'is_company': True,
            'company_id': self.company_id_1.id,
        })
        ext = self.env['integration.res.partner.external'].create({
            'integration_id': self.integration_no_api_1.id,
            'code': 'co-2',
            'name': mapped_company.name,
        })
        self.env['integration.res.partner.mapping'].create({
            'integration_id': self.integration_no_api_1.id,
            'external_partner_id': ext.id,
            'partner_id': mapped_company.id,
        })

        proxy = self._create_proxy('customer', {
            'person_name': 'Z',
            'email': 'z@test.com',
            'company_name': 'Company 1',
        })
        self.integration_no_api_1.write({'skip_individual_contacts': True})
        self.assertTrue(proxy._is_mapping_compatible(mapped_company))

    def test_mapping_compatibility_company_in_individual_mode_rejects(self):
        """mapped is company, skip_individual=False -> reject."""
        mapped_company = self.env['res.partner'].create({
            'name': 'Company 1',
            'is_company': True,
            'company_id': self.company_id_1.id,
        })
        ext = self.env['integration.res.partner.external'].create({
            'integration_id': self.integration_no_api_1.id,
            'code': 'co-3',
            'name': mapped_company.name,
        })
        self.env['integration.res.partner.mapping'].create({
            'integration_id': self.integration_no_api_1.id,
            'external_partner_id': ext.id,
            'partner_id': mapped_company.id,
        })

        proxy = self._create_proxy('customer', {
            'person_name': 'A',
            'email': 'a@test.com',
            'company_name': 'Company 1',
        })
        self.integration_no_api_1.write({'skip_individual_contacts': False})
        self.assertFalse(proxy._is_mapping_compatible(mapped_company))

    def test_mapping_compatibility_parent_company_id_differs_from_integration_rejects(self):
        """mapped_partner.parent_id.company_id != integration.company_id -> reject."""
        # Parent in another company
        parent_company_2 = self.env['res.partner'].create({
            'name': 'Company 2',
            'is_company': True,
            'company_id': self.company_id_2.id,
        })

        # The contact belongs to the same company as the integration (company_id_1) -> let's go through the early guard
        contact = self.env['res.partner'].create({
            'name': 'Child of Co2',
            'is_company': False,
            'company_id': self.company_id_1.id,
            'parent_id': parent_company_2.id,
        })
        ext = self.env['integration.res.partner.external'].create({
            'integration_id': self.integration_no_api_1.id,
            'code': 'c-3',
            'name': contact.name,
        })
        self.env['integration.res.partner.mapping'].create({
            'integration_id': self.integration_no_api_1.id,
            'external_partner_id': ext.id,
            'partner_id': contact.id,
        })

        proxy = self._create_proxy('customer', {
            'person_name': 'B',
            'email': 'b@test.com',
            'company_name': 'Company 2',
        })
        # But the integration is tied to company_id_1, whereas parent.company_id == company_id_2
        self.assertFalse(proxy._is_mapping_compatible(contact))

    def test_mapping_compatibility_company_only_same_name_but_different_company_id_rejects(self):
        """skip_individual=True; mapped company == expected by name, but company_id differs -> reject."""
        # Company X in another Odoo company
        mapped_company_other = self.env['res.partner'].create({
            'name': 'Company X',
            'is_company': True,
            'company_id': self.company_id_2.id,
        })
        ext = self.env['integration.res.partner.external'].create({
            'integration_id': self.integration_no_api_1.id,
            'code': 'co-x',
            'name': mapped_company_other.name,
        })
        self.env['integration.res.partner.mapping'].create({
            'integration_id': self.integration_no_api_1.id,
            'external_partner_id': ext.id,
            'partner_id': mapped_company_other.id,
        })

        # In the context, we ask for the same company by name
        # (so that mapped_partner == company from the record's perspective)
        # but _get_or_create_company() will create/take Company X in company_id_1,
        # and the final company_id check will trigger a reject.
        proxy = self._create_proxy('customer', {
            'person_name': 'C',
            'email': 'c@test.com',
            'company_name': 'Company X',
        })
        self.integration_no_api_1.write({'skip_individual_contacts': True})
        self.assertFalse(proxy._is_mapping_compatible(mapped_company_other))

    def test_address_uniqueness_ignores_non_critical_fields(self):
        """Test that non-critical fields are ignored in address uniqueness check."""
        contact = self.env['res.partner'].create({
            'name': 'Address Test',
            'type': 'contact',
            'street': 'Old St',
        })

        new_vals = {
            'street': 'Old St',
            'lang': 'en_US',
            'category_id': [(6, 0, [])],
        }

        proxy = self._create_proxy('shipping_address', {
            'person_name': 'Addr Test',
            'email': 'addr@test.com',
            'street': 'Old St',
        })

        has_changes = proxy._has_address_changes(contact, new_vals)
        self.assertFalse(has_changes)

    def test_multi_company_isolation(self):
        """Test that integration respects company boundaries."""
        factory = self.env['integration.res.partner.factory'].create({
            'integration_id': self.integration_no_api_2.id,
        })

        data = {
            'person_name': 'Cross Company Test',
            'email': 'cross@test.com',
        }

        proxy = self.env['integration.res.partner.proxy'].create_proxy(
            type_='customer',
            integration_id=self.integration_no_api_2.id,
            factory_id=factory.id,
            data=data,
        )

        partner = proxy.get_or_create_partner()

        self.assertEqual(self.integration_no_api_2.company_id.id, partner.company_id.id)
        self.assertEqual(partner.company_id.id, self.company_id_2.id)
        self.assertNotEqual(partner.company_id.id, self.company_id_1.id)

    def test_skip_individual_contacts_mode_creates_company_contact(self):
        """Test that in skip_individual mode, company contact is returned."""
        self.integration_no_api_1.write({'skip_individual_contacts': True})

        data = {
            'company_name': 'Skip Individual Corp',
            'person_name': 'John Doe',
            'email': 'john@skip.com',
        }
        proxy = self._create_proxy('customer', data)
        partner = proxy.get_or_create_partner()

        self.assertTrue(partner.is_company)
        self.assertEqual(partner.name, 'Skip Individual Corp')

    def test_archived_mapped_partner_is_ignored_and_new_contact_created(self):
        """If mapped partner is archived, mapping must be ignored and a new partner must be created."""
        # Archived partner that is currently mapped
        archived_partner = self.env['res.partner'].create({
            'name': 'Archived Mapped Contact',
            'is_company': False,
            'company_id': self.company_id_1.id,
            'active': False,
            'email': 'archived@example.com',
        })

        ext_record = self.env['integration.res.partner.external'].create({
            'integration_id': self.integration_no_api_1.id,
            'code': 'ext-arch-1',
            'name': archived_partner.name,
        })

        mapping = self.env['integration.res.partner.mapping'].create({
            'integration_id': self.integration_no_api_1.id,
            'external_partner_id': ext_record.id,
            'partner_id': archived_partner.id,
        })

        # Proxy that will try to use mapping by external_id
        proxy = self._create_proxy('customer', {
            'id': 'ext-arch-1',
            'person_name': 'John New',
            'email': 'john.new@example.com',
        })
        self.assertTrue(proxy)

        partner = proxy.get_or_create_partner()

        # Must not reuse archived mapped partner
        self.assertTrue(partner)
        self.assertNotEqual(partner.id, archived_partner.id)
        self.assertTrue(partner.active)

        # Mapping must be updated to the new partner (same record, partner_id rewritten)
        mapping.invalidate_recordset()
        self.assertEqual(mapping.partner_id.id, partner.id)
