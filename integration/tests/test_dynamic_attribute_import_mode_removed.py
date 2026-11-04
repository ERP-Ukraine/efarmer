# See LICENSE file for full copyright and licensing details.

import json

from odoo.tests import tagged

from .config.integration_init import OdooIntegrationInit


@tagged('post_install', '-at_install', 'test_integration_core')
class TestDynamicAttributeImportModeRemoved(OdooIntegrationInit):
    """The "Dynamic Attribute Import Mode" setting is gone: new attributes always get the default mode."""

    REMOVED_SETTING = 'is_import_dynamic_attribute'

    def _export_settings(self):
        wizard = self.env['import.export.integration.wizard'].create({'integration_id': self.integration_no_api_1.id})
        wizard.action_export()

        return json.loads(wizard.output)

    def test_setting_is_removed_from_integration(self):
        self.assertNotIn(self.REMOVED_SETTING, self.env['sale.integration']._fields)

    def test_new_attribute_is_created_with_default_mode(self):
        external_attribute = self.env['integration.product.attribute.external'].create({
            'integration_id': self.integration_no_api_1.id,
            'code': 'dyn_attr_removed',
            'name': 'Dyn Attr Removed',
        })

        self.assertEqual(external_attribute._get_mode_create_variant('dyn_attr_removed', []), 'always')

    def test_export_has_no_removed_setting(self):
        self.assertNotIn(self.REMOVED_SETTING, self._export_settings())

    def test_import_of_old_file_with_removed_key(self):
        integration = self.integration_no_api_1
        data = self._export_settings()
        data[self.REMOVED_SETTING] = True
        data['allow_import_images'] = not integration.allow_import_images
        expected_images = data['allow_import_images']

        wizard = self.env['import.export.integration.wizard'].create({
            'integration_id': integration.id,
            'input': json.dumps(data),
        })
        wizard.import_data()

        self.assertEqual(wizard.state, 'finish')
        # The rest of the file is still applied, only the removed key is ignored
        self.assertEqual(integration.allow_import_images, expected_images)
        self.assertNotIn(self.REMOVED_SETTING, integration._fields)
