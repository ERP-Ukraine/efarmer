# Copyright 2021 VentorTech OU
# See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import TestPrintNodeCommon


@tagged('post_install', '-at_install', 'pn_ir_cron')
class TestPrintNodeIrCron(TestPrintNodeCommon):
    """
    Tests of IrCron model methods
    """

    def setUp(self):
        super().setUp()

        self.scenario.update({
            'action': self.env.ref('printnode_base.print_product_labels_on_transfer').id,
            'report_id': self.env.ref('stock.label_product_product').id,
        })

        self.cron = self.env['ir.cron'].create({
            'active': False,
            'name': 'TestCronCreateMove',
            'user_id': self.env.ref('base.user_root').id,
            'model_id': self.env.ref('stock.model_stock_picking').id,
            'state': 'code',
            'code': 'model.search([("name", "=", "Test Stock Picking")]).button_validate()',
            'interval_number': 1,
            'interval_type': 'days',
        })

        # Create Mock objects
        self.mock_scenario_print_product_labels_on_transfer = self._create_patch_object(
            type(self.stock_picking),
            '_scenario_print_product_labels_on_transfer',
        )
        self.mock_scenario_print_product_labels_on_transfer.return_value = True

        self.mock_get_printer = self._create_patch_object(
            type(self.scenario),
            '_get_printer',
        )

    def _set_up_stock_move(self):
        self.stock_move._action_confirm()
        self.stock_move._action_assign()
        self.stock_move.move_line_ids.quantity = 2

    def test_run_print_scenario_from_cron_case_1(self):
        self._set_up_stock_move()

        self.assertFalse(self.product_id.stock_quant_ids)

        cron = (
            self.cron
            .with_user(self.cron.user_id)
            .with_context(allowed_company_ids=[self.company.id])
            .with_company(self.company)
        )

        cron.env.company.printnode_enabled = False

        cron.ir_actions_server_id.run()

        self.assertEqual(
            self.product_id.stock_quant_ids.filtered(
                lambda q: q.location_id == self.location_dest
            )[:1].quantity,
            2,
        )

        self.mock_scenario_print_product_labels_on_transfer.assert_not_called()
        self.mock_get_printer.assert_not_called()

    def test_run_print_scenario_from_cron_case_2(self):
        """Printnode enabled, but printing from crons disabled -> scenario must NOT run."""

        # Set Up
        self._set_up_stock_move()

        # Company flags
        self.company.printnode_enabled = True
        self.company.printing_scenarios_from_crons = False

        self.assertFalse(self.product_id.stock_quant_ids)

        # Run as cron user in the right company (Odoo 19 way)
        cron = (
            self.cron
            .with_user(self.cron.user_id)
            .with_context(allowed_company_ids=[self.company.id])
            .with_company(self.company)
        )

        # Run the server action code (no commit/rollback)
        cron.ir_actions_server_id.run()

        # Stock moved & validated
        self.assertEqual(
            self.product_id.stock_quant_ids.filtered(
                lambda q: q.location_id == self.location_dest
            )[:1].quantity,
            2,
        )

        # Ensure print scenario wasn't executed
        self.mock_scenario_print_product_labels_on_transfer.assert_not_called()
        self.mock_get_printer.assert_not_called()

    def test_run_print_scenario_from_cron_case_3(self):
        """Printnode enabled + printing from crons enabled -> scenario must run."""

        # Set Up
        self._set_up_stock_move()
        self.mock_get_printer.return_value = self.printer, self.printer_bin

        # Company flags: printing from crons enabled
        self.company.printnode_enabled = True
        self.company.printing_scenarios_from_crons = True

        self.assertFalse(self.product_id.stock_quant_ids)

        # Run as cron user in the right company (Odoo 19 way)
        cron = (
            self.cron
            .with_user(self.cron.user_id)
            .with_context(allowed_company_ids=[self.company.id])
            .with_company(self.company)
        )

        # Run the server action code (no commit/rollback)
        cron.ir_actions_server_id.run()

        # Stock moved & validated
        self.assertEqual(
            self.product_id.stock_quant_ids.filtered(
                lambda q: q.location_id == self.location_dest
            )[:1].quantity,
            2,
        )

        # Ensure print scenario executed
        self.mock_scenario_print_product_labels_on_transfer.assert_called_once()
        self.mock_get_printer.assert_called_once()

    def test_run_print_scenario_from_cron_case_4(self):
        """ Test to check run/skip print scenario from cron
        """

        # Set Up
        self._set_up_stock_move()

        self.mock_get_printer.return_value = None
        self.mock_get_printer.side_effect = UserError("Test Exception - UserError")

        self.company.printnode_enabled = True
        self.company.printing_scenarios_from_crons = True

        cron = (
            self.cron
            .with_user(self.cron.user_id)
            .with_context(allowed_company_ids=[self.company.id])
            .with_company(self.company)
        )

        with self.assertRaises(UserError):
            cron.ir_actions_server_id.run()

        # Print scenario must not be executed (we fail before reaching it)
        self.mock_scenario_print_product_labels_on_transfer.assert_not_called()
        self.mock_get_printer.assert_called_once()
