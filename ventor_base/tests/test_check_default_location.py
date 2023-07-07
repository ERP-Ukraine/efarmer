# Copyright 2020 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo.tests.common import TransactionCase


class TestCheckDefaultLocation(TransactionCase):

    def setUp(self):
        super(TestCheckDefaultLocation, self).setUp()
        self.location = self.env['stock.location'].create({
            'name': 'test_location'
        })
        self.user = self.env['res.users'].create({
            'name': 'test_user',
            'login': 'test_user',
            'email': 'test.user@email.com'
        })
        self.ventor_worker = self.env.ref('ventor_base.ventor_role_wh_worker')
        self.ventor_worker.write({'users': [(4, self.user.id)]})
        self.inventory_manager = self.env.ref('stock.group_stock_manager')
        self.inventory_manager.write({'users': [(4, self.user.id)]})
        self.administration_settings = self.env.ref('base.group_system')
        self.administration_settings.write({'users': [(4, self.user.id)]})
        self.company = self.env['res.company'].create({
            'name': 'test_company',
        })
        self.product = self.env['product.template'].create({
            'name': 'new_product'
        })
