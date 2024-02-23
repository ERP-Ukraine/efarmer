# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).


from datetime import timedelta
from odoo.tests import Form
from odoo.tests.common import TransactionCase


class TestSaleOrderWorkflow(TransactionCase):

    def setUp(self):
        super().setUp()

        self.partner_id = self.env['res.partner'].create({
            'name': 'Test Partner',
        })
        self.so = self.env['sale.order'].create({
            'partner_id': self.partner_id.id,
        })
        self.product = self.env['product.product'].create({
            'name': 'Test Product',
            'type': 'product',
        })

    def _add_so_line(self, so, product, qty):
        sale_order_line = self.env['sale.order.line'].create({
            'order_id': so.id,
            'product_id': product.id,
            'product_uom_qty': qty,
        })
        return sale_order_line

    def test_state_transition_to_confirm(self):
        self.so.action_to_confirm()
        self.assertEqual(self.so.state, 'to_confirm')

    def test_state_transition_to_payment(self):
        self.so.action_to_payment()
        self.assertEqual(self.so.state, 'to_payment')

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

        sale_order_line = self._add_so_line(
            self.so, product, 1
        )
        self.assertEqual(sale_order_line.name, 'Test Template' + '\n' + 'For Sale')

    def test_order_pick_scheduled_date(self):
        self._add_so_line(self.so, self.product, 1)
        self.so.action_confirm()
        picking = self.so.picking_ids[0]

        self.assertEqual(
            self.so.pick_scheduled_date,
            picking.scheduled_date.date(),
            'Scheduled Delivery Date must be equal to Picking Scheduled Date.'
        )

        new_date = picking.scheduled_date + timedelta(days=1)
        picking.scheduled_date = new_date

        self.assertEqual(
            self.so.pick_scheduled_date,
            new_date.date(),
            'Scheduled Delivery Date must be equal to Picking Scheduled Date.'
        )

        picking.move_lines.quantity_done = 1.0
        picking.button_validate()
        self.assertFalse(self.sale_order.pick_scheduled_date)

    def test_pick_priority_no_backorder(self):
        self._add_so_line(self.so, self.product, 1)
        self.so.action_confirm()
        picking = self.so.picking_ids[0]
        self.so.priority = '1'

        self.assertEqual(
            picking.sale_priority,
            '1',
            'Sale Priority on Picking must be equal to SO priority.'
        )

        picking.move_lines.quantity_done = 1.0
        picking.button_validate()

        self.assertEqual(picking.state, 'done', 'Picking state should be done.')
        self.assertEqual(self.so.priority, '0', 'SO priority must be "Low priority".')
        self.assertEqual(
            picking.sale_priority,
            '0',
            'Picking Sale Priority must be "Low priority".'
        )

    def test_pick_priority_with_backorder(self):
        for _ in range(2):
            self._add_so_line(self.so, self.product, 1)
        self.so.priority = '1'
        self.so.action_confirm()

        # Deliver one product and create a backorder
        self.so.picking_ids.move_lines[0].quantity_done = 1
        backorder_wizard_dict = self.so.picking_ids.button_validate()
        backorder_wizard = Form(self.env[backorder_wizard_dict['res_model']].with_context(
            backorder_wizard_dict['context'])).save()
        backorder_wizard.process()

        # not all pickings are transfered, Sale Priority must not become "Low priority"
        for pick in self.so.picking_ids:
            self.assertEqual(
                pick.sale_priority, 
                '1',
                'Picking Sale Priority must be "Medium priority".'
            )
        self.assertEqual(self.so.priority, '1', 'SO priority must be still "Medium priority".')
