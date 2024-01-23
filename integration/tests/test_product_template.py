# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from .config.intuit_case import OdooIntegrationInit


class TestProductTemplate(OdooIntegrationInit):

    def setUp(self):
        super(TestProductTemplate, self).setUp()

    # integration/integration/models/product_template.py
    def test_get_integration_name_field(self):
        """
        Test 'get_integration_name_field' method.

        Verify that the 'get_integration_name_field' method correctly retrieves the integration
        name field based on the presence of the 'website_product_name' attribute.

        The 'website_product_name' field is used to store a more user-friendly product
        name for e-Commerce purposes. If this field is not empty, it will be used for sending
        data to the e-Commerce System instead of the standard field.

        The test first checks the default value of the name field ('name') and then updates the
        'website_product_name' attribute to verify that the method correctly returns the
        integration name field when it's set to 'website_product_name'.

        """
        # Testing when 'website_product_name' is not set (default behavior)
        self.assertEqual(
            self.product_pt_1.get_integration_name_field(),
            'name',
        )

        # Testing when 'website_product_name' is set
        self.product_pt_1.write({'website_product_name': 'Test Product 1 - Website'})
        self.assertEqual(
            self.product_pt_1.get_integration_name_field(),
            'website_product_name',
        )
