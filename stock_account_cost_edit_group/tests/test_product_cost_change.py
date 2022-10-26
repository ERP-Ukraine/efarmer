from odoo.exceptions import AccessError
from odoo.addons.stock_account.tests.test_stockvaluationlayer import TestStockValuationCommon


class TestProductCostChange(TestStockValuationCommon):
    @classmethod
    def setUpClass(cls):
        super(TestProductCostChange, cls).setUpClass()
        cls.product1.product_tmpl_id.categ_id.property_cost_method = 'average'
        cls.product1.product_tmpl_id.categ_id.property_valuation = 'real_time'
        cls.demo_user = cls.env.ref('base.user_demo')
        cls.group_can_edit_cost = cls.env.ref('stock_account_cost_edit_group.group_can_edit_product_cost')
        cls.group_stock_manager = cls.env.ref('stock.group_stock_manager')

    def test_00_product_cost_change_manual_avco(self):
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.product1.with_user(self.demo_user).write({'standard_price': 5})

    def test_01_product_cost_change_automatic_avco(self):
        self.product1.with_user(self.demo_user).sudo().write({'standard_price': 5})
        self.assertAlmostEqual(self.product1.standard_price, 5.00, 2)

    def test_02_product_cost_change_manual_avco_with_group(self):
        self.group_can_edit_cost.users |= self.demo_user
        # need access to stock.valueation.layer to change manually
        self.group_stock_manager.users |= self.demo_user
        self.product1.with_user(self.demo_user).write({'standard_price': 5})


