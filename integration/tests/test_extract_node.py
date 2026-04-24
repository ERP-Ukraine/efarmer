# See LICENSE file for full copyright and licensing details.

from odoo.tools import mute_logger
from odoo.tests import TransactionCase, tagged

from ..tools import ExtractNode


json_data = """
{
    "data": {
        "products": {
            "edges": [
                {
                    "node": {
                        "id": "100"
                    }
                },
                {
                    "node": {
                        "id": "200",
                        "name": "name-200"
                    }
                },
                {
                    "node": {
                        "id": "300",
                        "name": "name-300",
                        "child": {
                            "name": {
                                "child-name": "child-name-300"
                            },
                            "lines": [
                                {
                                    "id": 301
                                },
                                {
                                    "id": 302,
                                    "line_name": "line-name-302"
                                },
                                {
                                    "ID": 303
                                },
                                {
                                    "id": 304,
                                    "line_name": "line-name-304"
                                }
                            ]
                        }
                    }
                },
                {
                    "node": {
                        "name": "name-400"
                    }
                }
            ]
        },
        "errors": [
            "Error-1",
            "Error-2"
        ]
    },
    "code": 200
}
"""


@tagged('post_install', '-at_install', 'test_integration_core')
class TestShopifyExtractNode(TransactionCase):

    def setUp(self):
        super(TestShopifyExtractNode, self).setUp()

    def test_extract_node_code(self):
        result = ExtractNode.extract_raw(json_data, 'code', int)
        self.assertEqual(result, 200)

    @mute_logger('odoo.addons.integration.tools')
    def test_extract_node_errors(self):
        result = ExtractNode.extract_raw(json_data, 'data.errors', list)
        self.assertEqual(result, ['Error-1', 'Error-2'])

        result = ExtractNode.extract_raw(json_data, 'data.errors.0', str)
        self.assertEqual(result, 'Error-1')

        result = ExtractNode.extract_raw(json_data, 'data.errors.1', '')
        self.assertEqual(result, 'Error-2')

        result = ExtractNode.extract_raw(json_data, 'data.errors.2', '')
        self.assertEqual(result, '')

    @mute_logger('odoo.addons.integration.tools')
    def test_extract_node_products(self):
        result = ExtractNode.extract_raw(json_data, 'data.products.edges.node.id', list)
        self.assertEqual(result, ['100', '200', '300'])

        result = ExtractNode.extract_raw(json_data, 'data.products.edges.node.name', [])
        self.assertEqual(result, ['name-200', 'name-300', 'name-400'])

    @mute_logger('odoo.addons.integration.tools')
    def test_extract_node_product_child(self):
        result = ExtractNode.extract_raw(json_data, 'data.products.edges.2.node.child.name', {})
        self.assertEqual(result, {'child-name': 'child-name-300'})

        result = ExtractNode.extract_raw(json_data, 'data.products.edges.2.node.child.lines.ID', list)
        self.assertEqual(result, [303])

        result = ExtractNode.extract_raw(json_data, 'data.products.edges.2.node.child.lines.line_name', [])
        self.assertEqual(result, ['line-name-302', 'line-name-304'])

    @mute_logger('odoo.addons.integration.tools')
    def test_dropped_key(self):
        result = ExtractNode.extract_raw(json_data, 'code-x', '')
        self.assertEqual(result, '')

        result = ExtractNode.extract_raw(json_data, 'products.edges.node.id', list)
        self.assertEqual(result, [])

    def test_extract_from_python_object(self):
        data = {'products': [{'id': 100}, {'id': 200}]}

        result = ExtractNode.extract_raw(data, 'products.id', list)
        self.assertEqual(result, [100, 200])

        result = ExtractNode.extract_raw(data, 'products.1.id', int)
        self.assertEqual(result, 200)
