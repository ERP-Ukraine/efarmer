# -*- coding: utf-8 -*-
# Copyright 2026 VentorTech OU
# Part of Ventor modules. See LICENSE file for full copyright and licensing details.
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestAvailableLocations(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.env.company.id)], limit=1
        )
        cls.stock_location = cls.warehouse.lot_stock_id
        cls.picking_type = cls.warehouse.int_type_id
        cls.picking_type.active = True
        cls.allowed_location = cls.env["stock.location"].create(
            {"name": "Allowed", "location_id": cls.stock_location.id}
        )
        cls.allowed_sublocation = cls.env["stock.location"].create(
            {"name": "Allowed Shelf", "location_id": cls.allowed_location.id}
        )
        cls.forbidden_location = cls.env["stock.location"].create(
            {"name": "Forbidden", "location_id": cls.stock_location.id}
        )
        cls.product = cls.env["product.product"].create(
            {"name": "Test Product", "is_storable": True}
        )
        cls.user = cls.env["res.users"].create(
            {
                "name": "Restricted Stock User",
                "login": "restricted_stock_user",
                "groups_id": [(6, 0, [cls.env.ref("stock.group_stock_user").id])],
            }
        )

    def _create_picking(self, location, location_dest=None, env=None):
        env = env or self.env(user=self.user)
        location_dest = location_dest or self.allowed_sublocation
        return env["stock.picking"].create(
            {
                "picking_type_id": self.picking_type.id,
                "location_id": location.id,
                "location_dest_id": location_dest.id,
                "move_ids": [
                    (
                        0,
                        0,
                        {
                            "name": self.product.name,
                            "product_id": self.product.id,
                            "product_uom_qty": 1,
                            "product_uom": self.product.uom_id.id,
                            "location_id": location.id,
                            "location_dest_id": location_dest.id,
                        },
                    )
                ],
            }
        )

    def test_no_restriction_when_field_empty(self):
        picking = self._create_picking(self.forbidden_location, self.forbidden_location)
        picking.action_confirm()
        self.assertEqual(picking.state, "confirmed")

    def test_confirm_allowed_location_and_sublocation(self):
        self.user.available_location_ids = self.allowed_location
        for location in self.allowed_location | self.allowed_sublocation:
            picking = self._create_picking(location, location)
            picking.action_confirm()
            self.assertEqual(picking.state, "confirmed")

    def test_confirm_forbidden_source_location(self):
        self.user.available_location_ids = self.allowed_location
        picking = self._create_picking(self.forbidden_location)
        with self.assertRaises(UserError):
            picking.action_confirm()
        self.assertEqual(picking.state, "draft")

    def test_confirm_forbidden_destination_location(self):
        self.user.available_location_ids = self.allowed_location
        picking = self._create_picking(self.allowed_location, self.forbidden_location)
        with self.assertRaises(UserError):
            picking.action_confirm()
        self.assertEqual(picking.state, "draft")

    def test_validate_draft_with_forbidden_location(self):
        self.user.available_location_ids = self.allowed_location
        for location, location_dest in (
            (self.forbidden_location, self.allowed_location),
            (self.allowed_location, self.forbidden_location),
        ):
            picking = self._create_picking(location, location_dest)
            with self.assertRaises(UserError):
                picking.button_validate()

    def test_change_to_forbidden_source_location_after_confirm(self):
        self.user.available_location_ids = self.allowed_location
        picking = self._create_picking(self.allowed_location)
        picking.action_confirm()
        with self.assertRaises(UserError):
            picking.location_id = self.forbidden_location
        picking.location_id = self.allowed_sublocation
        self.assertEqual(picking.move_ids.location_id, self.allowed_sublocation)

    def test_change_to_forbidden_destination_location_after_confirm(self):
        self.user.available_location_ids = self.allowed_location
        picking = self._create_picking(self.allowed_location, self.allowed_location)
        picking.action_confirm()
        with self.assertRaises(UserError):
            picking.location_dest_id = self.forbidden_location
        picking.location_dest_id = self.allowed_sublocation
        self.assertEqual(picking.move_ids.location_dest_id, self.allowed_sublocation)

    def test_change_location_of_chained_picking(self):
        first_picking = self._create_picking(self.allowed_location, env=self.env)
        second_picking = self._create_picking(
            self.allowed_sublocation, self.stock_location, env=self.env
        )
        second_picking.move_ids.write(
            {
                "move_orig_ids": [(6, 0, first_picking.move_ids.ids)],
                "procure_method": "make_to_order",
            }
        )
        (first_picking | second_picking).action_confirm()
        with self.assertRaises(UserError):
            second_picking.location_id = self.forbidden_location
        self.assertEqual(second_picking.move_ids.move_orig_ids, first_picking.move_ids)
        # Changing the destination location keeps the chain.
        second_picking.location_dest_id = self.forbidden_location
        self.assertEqual(second_picking.move_ids.move_orig_ids, first_picking.move_ids)
