# See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase, tagged

from .config.integration_init import OdooIntegrationInit
from ...integration import tools


@tagged('post_install', '-at_install', 'test_integration_core')
class TestTools(OdooIntegrationInit, TransactionCase):

    def setUp(self):
        super(TestTools, self).setUp()

    # integration/integration/tools.py
    def test_normalize_uom_name(self):
        """
        Test the 'normalize_uom_name' function.

        This test evaluates the behavior of the 'normalize_uom_name' function by providing
        different unit of measure (UOM) names:
        1. It checks if the function correctly normalizes 'kg' to 'kg'.
        2. It verifies that 'Kg' is normalized to 'kg'.
        3. It ensures that 'kgs' is normalized to 'kg'.
        4. It checks if 'lbs' is correctly normalized to 'lb'.
        5. It verifies that 'Lbs' is normalized to 'lb'.

        The test covers various UOM name variations and ensures that 'normalize_uom_name'
        returns the expected results.
        """
        self.assertEqual(tools.normalize_uom_name('kg'), 'kg')
        self.assertEqual(tools.normalize_uom_name('Kg'), 'kg')
        self.assertEqual(tools.normalize_uom_name('kgs'), 'kg')
        self.assertEqual(tools.normalize_uom_name('lbs'), 'lb')
        self.assertEqual(tools.normalize_uom_name('Lbs'), 'lb')
