# See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'test_supports_returns_refunds')
class TestSupportsReturnsRefunds(TransactionCase):
    """The Returns & Refunds tab is opened by the connector's own `supports_returns_refunds` flag."""

    SUPPORTED = {'shopify', 'woocommerce'}

    def test_flag_is_true_only_for_connectors_with_returns_support(self):
        integration_model = self.env['sale.integration']
        types = [key for key, _label in integration_model._fields['type_api'].selection]

        for type_api in types:
            with self.subTest(type_api=type_api):
                integration = integration_model.new({'type_api': type_api})

                self.assertEqual(integration.supports_returns_refunds, type_api in self.SUPPORTED)

    def test_form_view_loads_the_flag(self):
        """A field used in an `invisible` expression must be loaded in the view, or the client sees undefined."""
        arch = self.env['sale.integration'].get_view(
            view_id=self.env.ref('integration.view_sale_integration_form').id,
        )['arch']

        self.assertIn('name="supports_returns_refunds"', arch)
