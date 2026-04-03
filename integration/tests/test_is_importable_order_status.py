# See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged
from odoo.tests.common import mute_logger

from .config.integration_init import OdooIntegrationInit, load_xml
from ..exceptions import IntegrationNotImplementedError


@tagged('post_install', '-at_install')
class TestIsImportableOrderStatus(OdooIntegrationInit):
    """Test is_importable_order_status method for base integration."""

    @classmethod
    def setUpClass(cls):
        super(TestIsImportableOrderStatus, cls).setUpClass()
        # Load base integration XML data first (needed for refs)
        load_xml(
            cls.env,
            module='integration',
            path_file='tests/data',
            filename='init_sale_integration.xml',
        )
        # Create a base integration for testing once per class
        company_id_1 = cls.env.ref('integration.test_integration_company_1')
        cls.base_integration = cls.env['sale.integration'].create({
            'name': 'Test Base Integration',
            'type_api': 'no_api',
            'company_id': company_id_1.id,
        })

    def test_base_integration_raises_not_implemented_error(self):
        """Test base integration raises NotImplementedError."""
        with mute_logger('odoo.tools.translate'):
            with self.assertRaises(IntegrationNotImplementedError) as context:
                self.base_integration.is_importable_order_status(['pending'])

        self.assertIn("must be implemented by each connector", str(context.exception))
