# Copyright 2026 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import AccessError
from odoo.tests import tagged

MSG = "You do not have permission to reset posted customer invoices to draft or cancel them."


@tagged("post_install", "-at_install")
class TestInvoiceCancelRestrict(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        group = cls.env.ref(
            "account_invoice_cancel_restrict.group_cancel_posted_customer_invoice")
        base_groups = [
            Command.link(cls.env.ref("account.group_account_invoice").id),
            Command.link(cls.env.ref("base.group_user").id),
        ]
        # sudo(): creating users/partners is setup, not what we test. The test
        # framework's default user may lack "Contact Creation" rights.
        users = cls.env["res.users"].sudo().with_context(no_reset_password=True)
        common = {
            "company_id": cls.env.company.id,
            "company_ids": [Command.set(cls.env.company.ids)],
        }
        cls.user_regular = users.create(
            {**common, "name": "Regular", "login": "regular_inv",
             "groups_id": base_groups})
        cls.user_allowed = users.create(
            {**common, "name": "Allowed", "login": "allowed_inv",
             "groups_id": base_groups + [Command.link(group.id)]})

    def _invoice(self, move_type="out_invoice", post=True):
        move = self.init_invoice(move_type, amounts=[100.0])
        if post:
            move.action_post()
        return move

    def _as(self, move, user):
        return move.with_user(user)

    # --- Authorized user -------------------------------------------------

    def test_allowed_user_can_reset_and_cancel(self):
        inv = self._invoice()
        self._as(inv, self.user_allowed).button_draft()
        self.assertEqual(inv.state, "draft")
        self._as(inv, self.user_allowed).button_cancel()
        self.assertEqual(inv.state, "cancel")
        self._as(inv, self.user_allowed).button_draft()
        self.assertEqual(inv.state, "draft")
        self.assertFalse(self._as(inv, self.user_allowed).restrict_customer_invoice_cancel)

    def test_allowed_user_cancel_from_posted(self):
        inv = self._invoice()
        self._as(inv, self.user_allowed).button_cancel()
        self.assertEqual(inv.state, "cancel")

    def test_regular_user_cannot_reset_posted(self):
        inv = self._invoice()
        with self.assertRaisesRegex(AccessError, MSG):
            self._as(inv, self.user_regular).button_draft()
        self.assertEqual(inv.state, "posted")

    def test_regular_user_cannot_cancel_posted(self):
        inv = self._invoice()
        with self.assertRaisesRegex(AccessError, MSG):
            self._as(inv, self.user_regular).button_cancel()
        self.assertEqual(inv.state, "posted")

    def test_regular_user_cannot_cancel_previously_posted_draft(self):
        inv = self._invoice()
        inv.sudo().button_draft()
        self.assertTrue(inv.posted_before)
        self.assertTrue(self._as(inv, self.user_regular).restrict_customer_invoice_cancel)
        with self.assertRaisesRegex(AccessError, MSG):
            self._as(inv, self.user_regular).button_cancel()

    def test_regular_user_cannot_reset_cancelled_posted_invoice(self):
        inv = self._invoice()
        inv.sudo().button_cancel()
        with self.assertRaisesRegex(AccessError, MSG):
            self._as(inv, self.user_regular).button_draft()

    def test_bulk_action_blocked(self):
        invs = self._invoice() | self._invoice() | self._invoice("out_invoice", post=False)
        with self.assertRaisesRegex(AccessError, MSG):
            self._as(invs, self.user_regular).button_draft()
        with self.assertRaisesRegex(AccessError, MSG):
            self._as(invs, self.user_regular).button_cancel()
        self.assertEqual(invs[:2].mapped("state"), ["posted", "posted"])

    def test_direct_write_blocked(self):
        inv = self._invoice()
        for vals in ({"state": "draft"}, {"state": "cancel"}, {"posted_before": False}):
            with self.assertRaisesRegex(AccessError, MSG):
                self._as(inv, self.user_regular).write(vals)
        self.assertEqual(inv.state, "posted")

    def test_rpc_style_call_blocked(self):
        """Simulates an external API call: call_kw on the model method."""
        from odoo.api import call_kw
        inv = self._invoice()
        env = inv.with_user(self.user_regular).env
        with self.assertRaisesRegex(AccessError, MSG):
            call_kw(env["account.move"], "button_draft", [inv.ids], {})

    def test_regular_user_create_edit_post_new_invoice(self):
        inv = self.env["account.move"].with_user(self.user_regular).create({
            "move_type": "out_invoice",
            "partner_id": self.partner_a.id,
            "invoice_line_ids": [Command.create({
                "product_id": self.product_a.id, "price_unit": 50.0})],
        })
        inv.invoice_line_ids.price_unit = 75.0
        inv.action_post()
        self.assertEqual(inv.state, "posted")

    def test_regular_user_can_cancel_never_posted_draft(self):
        inv = self._invoice(post=False)
        self._as(inv, self.user_regular).button_cancel()
        self.assertEqual(inv.state, "cancel")
        self._as(inv, self.user_regular).button_draft()
        self.assertEqual(inv.state, "draft")

    def test_vendor_bills_and_credit_notes_untouched(self):
        for move_type in ("in_invoice", "out_refund", "in_refund"):
            move = self._invoice(move_type)
            self.assertFalse(self._as(move, self.user_regular).restrict_customer_invoice_cancel)
            self._as(move, self.user_regular).button_draft()
            self.assertEqual(move.state, "draft")
            self._as(move, self.user_regular).button_cancel()
            self.assertEqual(move.state, "cancel")

    def test_standard_restrictions_preserved_for_allowed_user(self):
        inv = self._invoice()
        inv.button_hash()  # lock with an inalterable hash
        with self.assertRaisesRegex(Exception, "locked"):
            self._as(inv, self.user_allowed).button_draft()
