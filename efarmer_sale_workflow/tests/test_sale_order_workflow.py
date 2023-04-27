# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).


from datetime import timedelta

from odoo.tests.common import TransactionCase


class TestSaleOrderWorkflow(TransactionCase):

    def setUp(self):
        super().setUp()

        self.sale_order = self.env['sale.order'].create({
            'partner_id': self.env.ref('base.res_partner_1').id,
        })

        self.product = self.env['product.product'].create({
            'name': 'Test Product',
            'type': 'product',
        })

    def test_state_transition_to_confirm(self):
        self.sale_order.action_to_confirm()
        self.assertEqual(self.sale_order.state, 'to_confirm')

    def test_state_transition_to_payment(self):
        self.sale_order.action_to_payment()
        self.assertEqual(self.sale_order.state, 'to_payment')

    def test_order_line_name(self):
        """
            Test value of field name in SO line.
            Expect to receive result of redefining get_product_multiline_description_sale()
        """
        test_attr = self.env['product.attribute'].create({
            'name': 'Test'
        })
        attr = self.env['product.attribute.value'].create({
            'name': 'Attribute',
            'attribute_id': test_attr.id
        })
        product_template = self.env['product.template'].create({
            'name': 'Test Template',
            'description_sale': 'For Sale',
            'attribute_line_ids': [(0, 0, {
                'attribute_id': test_attr.id,
                'value_ids': [(6, 0, [attr.id])],
            })]
        })
        product = product_template.product_variant_ids

        self.sale_order_line = self.env['sale.order.line'].create({
            'order_id': self.sale_order.id,
            'product_id': product.id,
        })

        self.assertEqual(self.sale_order_line.name, 'Test Template' + '\n' + 'For Sale')

    def test_order_pick_scheduled_date(self):
        self.sale_order_line = self.env['sale.order.line'].create({
            'order_id': self.sale_order.id,
            'product_id': self.product.id,
            'product_uom_qty': 1,
        })

        self.sale_order.action_confirm()
        picking = self.sale_order.picking_ids[0]

        self.assertEqual(
            self.sale_order.pick_scheduled_date,
            picking.scheduled_date.date(),
            'Scheduled Delivery Date must be equal to Picking Scheduled Date.'
        )

        new_date = picking.scheduled_date + timedelta(days=1)
        picking.scheduled_date = new_date

        self.assertEqual(
            self.sale_order.pick_scheduled_date,
            new_date.date(),
            'Scheduled Delivery Date must be equal to Picking Scheduled Date.'
        )
