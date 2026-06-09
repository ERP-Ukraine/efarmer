# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).


from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError


class TestOrderLineProductReplacementWizard(TransactionCase):

    def setUp(self):
        super().setUp()

        self.product_template = self.env["product.template"].create(
            {
                "name": "Product Template",
            }
        )
        self.product = self.create_product("Product")

        self.sale_order = self.env["sale.order"].create(
            {
                "partner_id": self.env.ref("base.res_partner_1").id,
            }
        )
        self.sale_order_line = self.env["sale.order.line"].create(
            {
                "order_id": self.sale_order.id,
                "product_id": self.product.id,
                "product_uom_qty": 10,
            }
        )

    def create_product(self, name, product_template=None):
        if not product_template:
            product_template = self.product_template
        product = self.env["product.product"].create(
            {
                "name": name,
                "product_tmpl_id": product_template.id,
            }
        )
        return product

    def test_apply_replacement_success(self):
        # create a replacement products for the sale order line
        replacement_product_1 = self.create_product("Replacement Product")
        replacement_product_2 = self.create_product("Replacement Product 2")

        # create the product replacements wizard and add the replacement products
        wizard = self.env["order.line.product.replacement.wizard"].create(
            {
                "product_tmpl_id": self.product_template.id,
                "sale_line_id": self.sale_order_line.id,
                "replacement_line_ids": [
                    (
                        0,
                        0,
                        {"product_id": replacement_product_1.id, "product_uom_qty": 5},
                    ),
                    (
                        0,
                        0,
                        {"product_id": replacement_product_2.id, "product_uom_qty": 5},
                    ),
                ],
            }
        )
        wizard.apply_replacement()

        # check that the sale order line was splited into 2 lines
        self.assertEqual(len(self.sale_order.order_line), 2)

        # check that the sale order lines have products defined in wizard
        order_lines = self.sale_order.order_line
        self.assertEqual(
            set(order_lines.mapped("product_id")),
            set([replacement_product_1, replacement_product_2]),
        )

        # check that the sale order lines have same quantity as before acting with wizard
        self.assertEqual(sum(order_lines.mapped("product_uom_qty")), 10)

    def test_apply_replacement_fail(self):
        # create the product replacements wizard and add the replacement products
        wizard = self.env["order.line.product.replacement.wizard"].create(
            {
                "product_tmpl_id": self.product_template.id,
                "sale_line_id": self.sale_order_line.id,
                "replacement_line_ids": [
                    (0, 0, {"product_id": self.product.id, "product_uom_qty": 5}),
                ],
            }
        )

        # qty in SO line is not equal to qty in wizard replacements,expect to receive ValidationError
        # "with self.assertRaises(ValidationError)" doesn't work here, use try/except constraction
        try:
            wizard.apply_replacement()
        except ValidationError:
            pass
        else:
            self.fail("Expected ValidationError, but no exception was raised")
