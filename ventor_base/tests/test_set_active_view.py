# Copyright 2020 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo.tests.common import TransactionCase
from odoo.exceptions import Warning
import base64


class TestSetActiveView(TransactionCase):
    def setUp(self):
        super(TestSetActiveView, self).setUp()
        self.view_with_barcode = self.env.ref('ventor_base.view_location_form_inherit_additional_barcode')
        self.ConfigObj = self.env['res.config.settings']

    def test_get_values(self):
        # A default value, adjusted in a view.xml
        config = self.ConfigObj.get_values()
        self.assertEqual(
            config['add_barcode_on_view'],
            False
        )
        # We set True directly to the ir.ui.view
        self.view_with_barcode.active = True
        config = self.ConfigObj.get_values()
        self.assertEqual(
            config['add_barcode_on_view'],
            True
        )

    def test_set_values(self):
        for value in (True, False):
            config = self.ConfigObj.create(
                {'add_barcode_on_view': value}
            )
            config.execute()
            self.assertEqual(
                self.view_with_barcode.active,
                value
            )
