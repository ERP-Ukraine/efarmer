# Copyright 2020 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError
from odoo.modules.module import get_resource_path
import base64


class TestCheckingLogotype(TransactionCase):

    def setUp(self):
        super(TestCheckingLogotype, self).setUp()
        self.user = self.env['res.users'].create({
            'name': 'admin',
            'login': 'login@email.com'
        })
        self.ventor_admin = self.env.ref('ventor_base.ventor_role_admin')
        self.ventor_admin.write({'users': [(4, self.user.id, 0)]})
        self.inventory_manager = self.env.ref('stock.group_stock_manager')
        self.inventory_manager.write({'users': [(4, self.user.id, 0)]})
        self.administration_settings = self.env.ref('base.group_system')
        self.administration_settings.write({'users': [(4, self.user.id, 0)]})
        self.company = self.env['res.company'].search([], limit=1)

    def test_upload_invalid_logo(self):
        img_path = get_resource_path('ventor_base', 'static', 'test_logo', '400_400.png')
        img_content = base64.b64encode(open(img_path, "rb").read())
        with self.assertRaises(UserError):
            self.company._validate_logotype({'logotype_file': img_content})

    def test_upload_valid_logo(self):
        img_path = get_resource_path('ventor_base', 'static', 'test_logo', '600_600.png')
        img_content = base64.b64encode(open(img_path, "rb").read())
        self.assertEqual(self.company._validate_logotype({'logotype_file': img_content}), True)
