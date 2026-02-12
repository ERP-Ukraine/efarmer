from unittest.mock import MagicMock

from odoo.tests import Form, TransactionCase


class TestKitCost(TransactionCase):

    def create_product(self, name, type="consu", standard_price=1.0):
        return self.env["product.product"].create(
            {
                "name": name,
                "type": type,
                "standard_price": standard_price,
            }
        )

    def create_bom(self, product, qty=1.0, type_="phantom"):
        return self.env["mrp.bom"].create(
            {
                "product_tmpl_id": product.product_tmpl_id.id,
                "product_id": product.id,
                "product_qty": qty,
                "type": type_,
            }
        )

    def create_so_with_one_product_by_form(self, partner, product):
        form = Form(self.env["sale.order"])
        form.partner_id = partner
        with form.order_line.new() as sol:
            sol.product_id = product
        return form.save()

    def test_has_kit_product(self):
        product = self.create_product("test")
        bom = self.create_bom(product)
        partner = self.env.ref("base.partner_admin")

        so = self.create_so_with_one_product_by_form(partner, product)
        sol = so.order_line.ensure_one()

        self.assertIs(sol.has_kit_product(), True)

    def test_cost_recomputation_after_order_confirmation(self):
        product = self.create_product("test")
        bom = self.create_bom(product)
        partner = self.env.ref("base.partner_admin")

        so = self.create_so_with_one_product_by_form(partner, product)

        mock = MagicMock()
        self.patch(
            type(self.env["product.product"]),
            "button_bom_cost",
            lambda *args: mock(*args),
        )

        so.action_confirm()
        mock.assert_called_once_with(product)

    def test_cost_recomputation_after_line_coping(self):
        product = self.create_product("test")
        bom = self.create_bom(product)
        partner = self.env.ref("base.partner_admin")

        so = self.create_so_with_one_product_by_form(partner, product)
        sol = so.order_line.ensure_one()

        mock = MagicMock()
        self.patch(
            type(self.env["product.product"]),
            "button_bom_cost",
            lambda *args: mock(*args),
        )

        sol.copy({"order_id": so.id})

        self.assertTrue(mock.called)
        mock.assert_any_call(product)
