# Copyright 2026 VentorTech OU
# See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import TestZldCommon


@tagged('post_install', '-at_install', 'zld_label')  # can be run by test-tag
class TestZldLabel(TestZldCommon):
    """
    Tests of selecting a record for the label preview (_get_preview_domain)
    and validating label fields (_validate_label_fields)
    """

    @classmethod
    def setUpClass(cls):
        super(TestZldLabel, cls).setUpClass()

        cls.Label = cls.env['zld.label']

    def test_get_preview_domain_fields(self):
        """
        Test that the domain requires stored fields used in the label to be set
        """

        domain = self.Label._get_preview_domain(self.env['product.product'], {
            'default_code': None,
            'FORMULA:doc.barcode[:5]': None,
            'FORMULA:doc.barcode or doc.default_code': None,
            # Fields not stored in the product variant table can't be used in the search domain
            'display_name': None,
            'FORMULA:doc.name[:5]': None,
        })

        self.assertEqual(domain, [
            ('default_code', '!=', False),
            ('barcode', '!=', False),
        ])

    def test_get_preview_domain_attributes(self):
        """
        Test that the domain requires all attributes used in the label, including attributes
        that don't create variants
        """

        fields = {
            "FORMULA:doc._get_attribute('Test Diameter')": None,
            'FORMULA:doc._get_attribute("Test Length")': None,
            # The same attribute in another formula doesn't add a condition
            "FORMULA:doc._get_attribute( 'Test Diameter' )[:2]": None,
        }

        for record, record_without_attributes in [
            (self.product_size_m, self.product_without_attributes),
            (self.product_tmpl, self.product_without_attributes.product_tmpl_id),
        ]:
            with self.subTest(model=record._name):
                Model = self.env[record._name]
                domain = self.Label._get_preview_domain(Model, fields)

                self.assertEqual(domain, [
                    ('attribute_line_ids.attribute_id', 'in', self.attribute_diameter.ids),
                    ('attribute_line_ids.attribute_id', 'in', self.attribute_length.ids),
                ])

                records = Model.search(domain)
                self.assertIn(record, records)
                self.assertNotIn(record_without_attributes, records)

    def test_get_preview_domain_translated_attribute(self):
        """
        Test that an attribute is found by its name in another installed language
        """

        fields = {"FORMULA:doc._get_attribute('Test Diámetro')": None}
        expected_domain = [('attribute_line_ids.attribute_id', 'in', self.attribute_diameter.ids)]

        domain = self.Label._get_preview_domain(self.env['product.product'], fields)
        self.assertEqual(domain, expected_domain)

        # An English name with a Spanish translation is found in the Spanish context as well
        domain = self.Label.with_context(lang='es_ES')._get_preview_domain(
            self.env['product.product'].with_context(lang='es_ES'),
            {"FORMULA:doc._get_attribute('Test Diameter')": None},
        )
        self.assertEqual(domain, expected_domain)

    def test_get_preview_domain_unknown_attribute(self):
        """
        Test that an unknown attribute doesn't add a condition
        """

        domain = self.Label._get_preview_domain(self.env['product.product'], {
            "FORMULA:doc._get_attribute('Test Unknown')": None,
            'default_code': None,
        })

        self.assertEqual(domain, [('default_code', '!=', False)])

    def test_get_preview_domain_other_models(self):
        """
        Test that attributes add no condition for models other than products
        """

        domain = self.Label._get_preview_domain(self.env['stock.lot'], {
            "FORMULA:doc.product_id._get_attribute('Test Diameter')": None,
        })

        self.assertEqual(domain, [('product_id', '!=', False)])

    def test_get_preview_domain_queries(self):
        """
        Test that attributes are searched by one query when their names are in the current
        language
        """

        fields = {
            "FORMULA:doc._get_attribute('Test Diameter')": None,
            "FORMULA:doc._get_attribute('Test Size')": None,
            "FORMULA:doc._get_attribute('Test Length')": None,
        }
        # Installed languages are cached on the first call
        self.env['res.lang'].get_installed()

        with self.assertQueryCount(1):
            domain = self.Label._get_preview_domain(self.env['product.product'], fields)

        self.assertEqual(len(domain), 3)

    def test_validate_label_fields_invalid_formula(self):
        """
        Test that a formula with invalid syntax is rejected, including formulas in related fields
        """

        # A valid formula passes
        self.Label._validate_label_fields('product.product', {
            "FORMULA:doc._get_attribute('Test Diameter')[:2]": None,
        })

        for fields in [
            {"FORMULA:doc._get_attribute('Test Diameter)": None},
            {'FORMULA:doc.name[:5': None},
            {'categ_id': {'FORMULA:doc.name[:5': None}},
        ]:
            with self.subTest(fields=fields):
                with self.assertRaises(UserError) as err:
                    self.Label._validate_label_fields('product.product', fields)

                self.assertIn('is invalid', str(err.exception))

    def test_preview_formula_can_use_time(self):
        """
        Test that a formula gets the time module in the preview, as it does when the label is printed
        """
        self.company.enable_formulas = True
        formula = "FORMULA:time.strftime('%Y') if doc.display_name else ''"

        data = self.Label._get_preview_data('product.product', {formula: None})

        self.assertTrue(data[formula])
