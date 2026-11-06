from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

V7M_1_2E_NAMESPACE = 'http://crd.gov.pl/wzor/2020/05/08/9393/'
V7M_2_NAMESPACE = 'http://crd.gov.pl/wzor/2021/12/27/11148/'
UNKNOWN_NAMESPACE = 'urn:unknown'


def jpk_xml(namespace):
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<tns:JPK xmlns:tns="{namespace}"/>'.encode()


@tagged('post_install', '-at_install')
class TestJPKDocumentType(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.v7m_1_2e_id = cls.env.ref('trilab_jpk_base.jpk_v7m_1_2_doc_type')
        cls.v7m_2_id = cls.env.ref('trilab_jpk_base.jpk_v7m_1_0_doc_type')

    def test_target_namespace(self):
        self.assertEqual(self.v7m_1_2e_id._get_target_namespace(), V7M_1_2E_NAMESPACE)
        self.assertEqual(self.v7m_2_id._get_target_namespace(), V7M_2_NAMESPACE)

    def test_find_by_namespace(self):
        type_ids = self.env['jpk.document.type']

        self.assertEqual(type_ids._find_by_namespace(V7M_1_2E_NAMESPACE), self.v7m_1_2e_id)
        self.assertFalse(type_ids._find_by_namespace(UNKNOWN_NAMESPACE))

    def test_other_form(self):
        with self.assertRaises(ValidationError) as context:
            self.v7m_2_id.validate_xml(jpk_xml(V7M_1_2E_NAMESPACE))

        self.assertEqual(str(context.exception), 'The file is JPK_V7M 1.2E, but the document type is JPK_V7M 1.0E')

    def test_unknown_namespace(self):
        with self.assertRaises(ValidationError) as context:
            self.v7m_2_id.validate_xml(jpk_xml(UNKNOWN_NAMESPACE))

        self.assertEqual(
            str(context.exception),
            f'The file namespace {UNKNOWN_NAMESPACE} does not match the document type JPK_V7M 1.0E',
        )

    def test_same_form_schema_errors(self):
        with self.assertRaises(ValidationError) as context:
            self.v7m_2_id.validate_xml(jpk_xml(V7M_2_NAMESPACE))

        self.assertIn("Element 'tns:JPK'", str(context.exception))
        self.assertNotIn('The file', str(context.exception))

    def test_default_namespace_prefix(self):
        with self.assertRaises(ValidationError) as context:
            self.v7m_2_id.validate_xml(f'<JPK xmlns="{V7M_2_NAMESPACE}"/>'.encode())

        self.assertIn("Element 'tns:JPK'", str(context.exception))
        self.assertNotIn('None:', str(context.exception))

    def test_error_count_and_position(self):
        xml_data = f'<tns:JPK xmlns:tns="{V7M_2_NAMESPACE}"><tns:Naglowek/><tns:Naglowek/></tns:JPK>'.encode()

        with self.assertRaises(ValidationError) as context:
            self.v7m_2_id.validate_xml(xml_data)

        header, *errors = str(context.exception).split('\n\n')
        self.assertEqual(header, 'Errors: 2')
        self.assertTrue(errors[0].endswith('/tns:JPK/tns:Naglowek[1] [1:63]: <tns:Naglowek/>'), errors[0])
        self.assertTrue(errors[1].endswith('/tns:JPK/tns:Naglowek[2] [1:78]: <tns:Naglowek/>'), errors[1])

    def test_all_schemas_load(self):
        for type_id in self.env['jpk.document.type'].search([('schema_path', '!=', False)]):
            with self.subTest(type=type_id.name), self.assertRaises(ValidationError) as context:
                type_id.validate_xml(jpk_xml(type_id._get_target_namespace()))

            self.assertTrue(str(context.exception).startswith('Errors: '), str(context.exception))
