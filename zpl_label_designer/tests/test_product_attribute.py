# Copyright 2026 VentorTech OU
# See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from .common import TestZldCommon


@tagged('post_install', '-at_install', 'zld_product_attribute')  # can be run by test-tag
class TestProductAttribute(TestZldCommon):
    """
    Tests of getting product attribute values for labels (_get_attribute)
    """

    def test_get_attribute_of_variant(self):
        """
        Test that a variant returns its own value of attributes that create variants
        """

        self.assertEqual(self.product_size_m._get_attribute('Test Diameter'), '22 mm')
        self.assertEqual(self.product_size_m._get_attribute('Test Size'), 'M')

    def test_get_attribute_of_variant_without_variants(self):
        """
        Test that a variant returns values of attributes that don't create variants
        """

        self.assertEqual(self.product_size_m._get_attribute('Test Length'), '2800 m')
        self.assertEqual(self.product_size_m._get_attribute('Test Material'), 'Wood, Metal')

    def test_get_attribute_of_template(self):
        """
        Test that a template returns all values of its attributes
        """

        self.assertEqual(self.product_tmpl._get_attribute('Test Diameter'), '22 mm')
        self.assertEqual(self.product_tmpl._get_attribute('Test Size'), 'S, M')
        self.assertEqual(self.product_tmpl._get_attribute('Test Length'), '2800 m')
        self.assertEqual(self.product_tmpl._get_attribute('Test Material'), 'Wood, Metal')

    def test_get_attribute_unknown(self):
        """
        Test that an empty string is returned for an attribute the product doesn't have
        """

        self.assertEqual(self.product_size_m._get_attribute('Test Unknown'), '')
        self.assertEqual(self.product_tmpl._get_attribute('Test Unknown'), '')
        self.assertEqual(self.product_without_attributes._get_attribute('Test Diameter'), '')
        self.assertEqual(
            self.product_without_attributes.product_tmpl_id._get_attribute('Test Diameter'),
            '',
        )

    def test_get_attribute_by_translated_name(self):
        """
        Test that an attribute can be found by its name in another installed language
        """

        self.assertEqual(self.product_size_m._get_attribute('Test Diámetro'), '22 mm')
        self.assertEqual(self.product_tmpl._get_attribute('Test Diámetro'), '22 mm')

    def test_get_attribute_translated_value(self):
        """
        Test that the value is returned in the language of the context
        """

        product_es = self.product_size_m.with_context(lang='es_ES')
        template_es = self.product_tmpl.with_context(lang='es_ES')

        self.assertEqual(product_es._get_attribute('Test Diameter'), '22 mm (ES)')
        self.assertEqual(product_es._get_attribute('Test Diámetro'), '22 mm (ES)')
        self.assertEqual(template_es._get_attribute('Test Diameter'), '22 mm (ES)')

    def test_get_attribute_current_language_first(self):
        """
        Test that the name in the language of the context wins when the same text is the name
        of different attributes in different languages
        """

        attribute_en = self._create_attribute('Test Shared', ['EN value'])
        attribute_en.update_field_translations('name', {'es_ES': 'Test Compartido'})
        attribute_es = self._create_attribute('Test Other', ['ES value'])
        attribute_es.update_field_translations('name', {'es_ES': 'Test Shared'})

        template = self._create_product_template('Test Product', attribute_en | attribute_es)
        product = template.product_variant_id

        product_es = product.with_context(lang='es_ES')
        template_es = template.with_context(lang='es_ES')

        self.assertEqual(product._get_attribute('Test Shared'), 'EN value')
        self.assertEqual(template._get_attribute('Test Shared'), 'EN value')
        self.assertEqual(product_es._get_attribute('Test Shared'), 'ES value')
        self.assertEqual(template_es._get_attribute('Test Shared'), 'ES value')

    def test_get_attribute_queries(self):
        """
        Test that the number of queries doesn't grow with the number of printed records
        """

        attribute_width = self._create_attribute('Test Width', ['10 mm', '20 mm', '30 mm'])
        attribute_coil = self._create_attribute(
            'Test Coil', ['Coil 1', 'Coil 2', 'Coil 3'], create_variant='no_variant')

        # Each product has its own values, as with technical attributes (width, length...)
        templates = self.env['product.template'].create([
            {
                'name': f'Test Product {width.name}',
                'attribute_line_ids': [
                    (0, 0, {'attribute_id': attribute_width.id, 'value_ids': [(6, 0, width.ids)]}),
                    (0, 0, {'attribute_id': attribute_coil.id, 'value_ids': [(6, 0, coil.ids)]}),
                ],
            }
            for width, coil in zip(attribute_width.value_ids, attribute_coil.value_ids)
        ])

        for records in [templates, templates.product_variant_ids]:
            for attr_name in ['Test Width', 'Test Coil', 'Test Unknown']:
                with self.subTest(model=records._name, attribute=attr_name):
                    self.assertEqual(
                        self._get_attribute_query_count(records, attr_name),
                        self._get_attribute_query_count(records[:1], attr_name),
                    )

    def test_get_attribute_as_user(self):
        """
        Test that a user without ZPL Label Designer rights gets attribute values (labels
        are printed by such users)
        """

        product = self.product_size_m.with_user(self.user)
        template = self.product_tmpl.with_user(self.user)

        self.assertEqual(product._get_attribute('Test Size'), 'M')
        self.assertEqual(product._get_attribute('Test Material'), 'Wood, Metal')
        self.assertEqual(template._get_attribute('Test Diámetro'), '22 mm')
