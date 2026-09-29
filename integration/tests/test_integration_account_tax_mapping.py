# See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from .config.returns_refunds_base import ReturnsRefundsAccountingTestBase


@tagged('post_install', '-at_install', 'test_integration_account_tax_mapping')
class TestIntegrationAccountTaxMapping(ReturnsRefundsAccountingTestBase):
    """Tests for integration.account.tax.mapping's company-branch scoping.

    Odoo enforces tax-name uniqueness across a company's whole branch tree, not per
    company (account.tax._constrains_name), so a mapping owned by a child company must
    be able to resolve a tax defined on a parent company — but never on an unrelated
    sibling that merely shares the same root.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.child_company = cls.env['res.company'].create({
            'name': 'Tax Mapping Child Co',
            'parent_id': cls.company.id,
            'country_id': cls.company.country_id.id,
        })
        cls.sibling_company = cls.env['res.company'].create({
            'name': 'Tax Mapping Sibling Co',
            'parent_id': cls.company.id,
            'country_id': cls.company.country_id.id,
        })

        tax_group = cls.env['account.tax.group'].search([], limit=1)

        cls.tax_on_parent = cls.env['account.tax'].with_company(cls.company).create({
            'name': 'Tax Mapping Parent Tax',
            'amount': 10,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'company_id': cls.company.id,
            'tax_group_id': tax_group.id,
            'country_id': cls.company.country_id.id,
        })
        cls.tax_on_sibling = cls.env['account.tax'].with_company(cls.sibling_company).create({
            'name': 'Tax Mapping Sibling Tax',
            'amount': 15,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'company_id': cls.sibling_company.id,
            'tax_group_id': tax_group.id,
            'country_id': cls.sibling_company.country_id.id,
        })

        cls.integration_on_child = cls._create_test_integration(
            'Tax Mapping Child Integration', company_id=cls.child_company.id,
        )

    def _create_mapping(self, external_name):
        external_tax = self.env['integration.account.tax.external'].create({
            'integration_id': self.integration_on_child.id,
            'code': 'tax-mapping-test-%s' % external_name,
            'name': external_name,
        })
        return self.env['integration.account.tax.mapping'].create({
            'integration_id': self.integration_on_child.id,
            'external_tax_id': external_tax.id,
        })

    def test_tax_id_domain_includes_parent_excludes_sibling(self):
        """The "Odoo Tax" field domain must resolve to the mapping's own company
        or any ancestor — never a sibling that only shares the same root."""
        mapping = self._create_mapping('domain-check')
        self.assertEqual(mapping.company_id, self.child_company)

        domain = eval(
            mapping._fields['tax_id'].domain, {'company_id': mapping.company_id.id},
        )
        matching = self.env['account.tax'].search(
            domain + [('id', 'in', (self.tax_on_parent | self.tax_on_sibling).ids)],
        )
        self.assertEqual(
            matching, self.tax_on_parent,
            'Domain must match the parent company\'s tax and exclude the sibling\'s.',
        )

    def test_fix_unmapped_by_search_resolves_tax_from_parent_company(self):
        """A mapping on the child company resolves a name-matched tax defined on
        the parent company — not just on the child's own company_id."""
        mapping = self._create_mapping(self.tax_on_parent.name)

        resolved = mapping._fix_unmapped_by_search()

        self.assertEqual(resolved, self.tax_on_parent)
        self.assertEqual(mapping.tax_id, self.tax_on_parent)

    def test_fix_unmapped_by_search_does_not_resolve_sibling_tax(self):
        """A same-named tax on an unrelated sibling company must never resolve,
        even though it shares the same root company as the mapping's own."""
        mapping = self._create_mapping(self.tax_on_sibling.name)

        resolved = mapping._fix_unmapped_by_search()

        self.assertFalse(resolved)
        self.assertFalse(mapping.tax_id)
