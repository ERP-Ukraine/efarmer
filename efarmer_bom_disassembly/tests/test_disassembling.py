from odoo.tests import Form, TransactionCase


class TestDisassembling(TransactionCase):

    def create_product(self, name, detailed_type='product', standard_price=1.0):
        return self.env['product.product'].create({
            'name': name,
            'detailed_type': detailed_type,
            'standard_price': standard_price,
        })

    def create_bom(self, product, qty=1.0, type_='phantom', disassembly=True):
        return self.env['mrp.bom'].create({
            'product_tmpl_id': product.product_tmpl_id.id,
            'product_id': product.id,
            'product_qty': qty,
            'disassembly': disassembly,
            'type': type_,
        })


    def create_bom_line(self, bom, product, qty=1.0):
        return self.env['mrp.bom.line'].create({
            'product_id': product.id,
            'product_qty': qty,
            'bom_id': bom.id,
        })

    def create_mo_by_form(self, product, bom, qty=1.0):
        mo_form = Form(self.env['mrp.production'])
        mo_form.product_id = product
        mo_form.product_qty = qty
        mo_form.bom_id = bom
        return mo_form.save()

    def test_recompute_product_cost_after_disassembling(self):
        box_cost = 1.0
        cup_cost = 10.0

        boxes_in_bom = 1.0
        cups_in_bom = 2.0

        box = self.create_product('box', standard_price=box_cost)
        cup = self.create_product('box', standard_price=cup_cost)
        box_with_cup = self.create_product('box with cup')

        bom = self.create_bom(box_with_cup)
        self.create_bom_line(bom, box, qty=boxes_in_bom)
        self.create_bom_line(bom, cup, qty=cups_in_bom)
        self.assertTrue(bom.disassembly)

        mo = self.create_mo_by_form(box_with_cup, bom)
        mo.action_confirm()
        mo.qty_producing = mo.product_qty
        for move in mo.move_raw_ids:
            move.quantity_done = move.product_uom_qty
        mo.button_mark_done()
        self.assertEqual(mo.state, 'done')

        self.assertEqual(box_with_cup.standard_price, box_cost * boxes_in_bom + cup_cost * cups_in_bom)
