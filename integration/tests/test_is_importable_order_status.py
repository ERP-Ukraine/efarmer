# See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged
from odoo.tests.common import mute_logger

from .config.integration_init import OdooIntegrationInit
from ..exceptions import IntegrationNotImplementedError


@tagged('post_install', '-at_install')
class TestIsImportableOrderStatus(OdooIntegrationInit):
    """Test is_importable_order_status method for base integration."""

    def setUp(self):
        super().setUp()
        # Create a base integration for testing
        self.base_integration = self.env['sale.integration'].create({
            'name': 'Test Base Integration',
            'type_api': 'no_api',
            'company_id': self.company_id_1.id,
        })

    def test_base_integration_raises_not_implemented_error(self):
        """Test base integration raises NotImplementedError."""
        with mute_logger('odoo.tools.translate'):
            with self.assertRaises(IntegrationNotImplementedError) as context:
                self.base_integration.is_importable_order_status(['pending'])

        self.assertIn("must be implemented by each connector", str(context.exception))
