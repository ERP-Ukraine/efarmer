# See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from odoo.tests import tagged, TransactionCase


@tagged('post_install', '-at_install', 'test_import_taxes_button')
class TestImportTaxesButton(TransactionCase):
    """The "Import Taxes" button of a tax mapping line imports the tax of that line only, and does not
    download the whole tax table of the store to do it."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.integration = cls.env['sale.integration'].create({
            'name': 'Import Taxes Button Integration',
            'type_api': 'no_api',
            'company_id': cls.env.company.id,
        })
        cls.mappings = cls.env['integration.account.tax.mapping']
        for code, rate in (('t1', '10.0'), ('t2', '20.0'), ('t3', '30.0')):
            external_tax = cls.env['integration.account.tax.external'].create({
                'integration_id': cls.integration.id,
                'code': code,
                'name': 'Button Tax %s' % code,
            })
            cls.mappings |= cls.env['integration.account.tax.mapping'].create({
                'integration_id': cls.integration.id,
                'external_tax_id': external_tax.id,
            })
        cls.mapping_1, cls.mapping_2, cls.mapping_3 = cls.mappings

        cls.store_taxes = {
            't1': {'id': 't1', 'name': 'Button Tax t1', 'rate': '10.0', 'tax_groups': []},
            't2': {'id': 't2', 'name': 'Button Tax t2', 'rate': '20.0', 'tax_groups': []},
        }

    def _patch_store(self, single_tax=None, full_list=None):
        """Replace the adapter of the integration with a store that records its calls."""
        calls = {'single': [], 'full': 0}

        class Store:

            def get_single_tax(self, tax_id):
                calls['single'].append(tax_id)
                return single_tax(tax_id)

            def get_taxes(self):
                calls['full'] += 1
                return full_list

        # The "no_api" adapter cannot be built at all, so the adapter property itself is replaced
        patcher = patch.object(type(self.integration), 'adapter', property(lambda integration: Store()))
        patcher.start()
        self.addCleanup(patcher.stop)

        return calls

    def test_button_on_a_line_requests_and_imports_only_that_tax(self):
        calls = self._patch_store(single_tax=lambda tax_id: dict(self.store_taxes.get(tax_id, {})))

        self.mapping_1.action_import_taxes_from_mapping()

        self.assertEqual(calls['single'], ['t1'], 'Only the tax of the line must be requested')
        self.assertEqual(calls['full'], 0, 'The whole tax table must not be requested')
        self.assertEqual(self.mapping_1.tax_id.name, 'Button Tax t1')
        self.assertEqual(self.mapping_1.tax_id.amount, 10.0)
        self.assertFalse(self.mapping_2.tax_id, 'The other lines must stay untouched')
        self.assertFalse(self.mapping_3.tax_id)

    def test_selected_taxes_are_requested_one_by_one(self):
        calls = self._patch_store(single_tax=lambda tax_id: dict(self.store_taxes.get(tax_id, {})))

        (self.mapping_1 | self.mapping_2).mapped('external_tax_id').action_import_taxes_from_external()

        self.assertEqual(sorted(calls['single']), ['t1', 't2'])
        self.assertEqual(calls['full'], 0)
        self.assertTrue(self.mapping_1.tax_id)
        self.assertTrue(self.mapping_2.tax_id)
        self.assertFalse(self.mapping_3.tax_id)

    def test_tax_that_is_gone_from_the_store_is_not_imported(self):
        self._patch_store(single_tax=lambda tax_id: {})

        result = self.mapping_3.action_import_taxes_from_mapping()

        self.assertFalse(self.mapping_3.tax_id)
        self.assertEqual(result['params']['type'], 'warning')

    def test_store_that_cannot_return_one_tax_falls_back_to_the_full_list_once(self):
        def not_implemented(tax_id):
            raise NotImplementedError

        calls = self._patch_store(single_tax=not_implemented, full_list=list(self.store_taxes.values()))

        (self.mapping_1 | self.mapping_2 | self.mapping_3).mapped('external_tax_id').action_import_taxes_from_external()

        self.assertEqual(calls['full'], 1, 'The full list is requested once for the whole selection')
        self.assertTrue(self.mapping_1.tax_id)
        self.assertTrue(self.mapping_2.tax_id)
        self.assertFalse(self.mapping_3.tax_id, 'A tax that is not in the list is not imported')
