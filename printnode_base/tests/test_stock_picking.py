# Copyright 2021 VentorTech OU
# See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from odoo.tests import tagged

from .common import TestPrintNodeCommon


@tagged('post_install', '-at_install', 'pn_stock_piking')  # can be run by test-tag
class TestPrintNodeStockPicking(TestPrintNodeCommon):
    """
    Tests of StockPicking model methods
    """

    def setUp(self):
        super(TestPrintNodeStockPicking, self).setUp()

        self.package = self.env['stock.package'].create({
            'name': 'Test package',
        })

        self.product = self.env['product.product'].create({
            'name': 'Test product',
            'is_storable': True,
        })

        self.source_location = self.env['stock.location'].create({
            'name': 'Source location',
            'usage': 'internal',
        })

        self.destination_location = self.env['stock.location'].create({
            'name': 'Destination location',
            'usage': 'internal',
        })

        self.test_stock_picking = self.env['stock.picking'].create({
            'location_id': self.env.ref('stock.stock_location_suppliers').id,
            'location_dest_id': self.location_dest.id,
            'move_type': 'direct',
            'picking_type_id': self.picking_type_incoming.id,
            'move_line_ids': [(0, 0, {
                'product_id': self.product.id,
                'quantity': 1,
                'location_id': self.source_location.id,
                'location_dest_id': self.destination_location.id,
            })]
        })

    def test_scenario_print_package_on_put_in_pack(self):
        """
        Test _scenario_print_package_on_put_in_pack method
        """

        test_objects_for_print = self.env[self.scenario.model_id.model].search([])

        with self.cr.savepoint(), patch.object(
            type(self.env['printnode.printer']),
            'printnode_print',
        ) as mock_printnode_printer:
            self.env['stock.picking']._scenario_print_package_on_put_in_pack(
                report_id=self.so_report,
                printer_id=self.printer,
                number_of_copies=1,
                packages_to_print=test_objects_for_print
            )
            mock_printnode_printer.assert_called_once_with(
                self.so_report,
                test_objects_for_print,
                copies=1,
                options={},
            )

    def test_scenario_print_document_on_picking_status_change(self):
        """
        Test _scenario_print_document_on_picking_status_change method
        """

        stock_picking = self.env['stock.picking'].search([], limit=1)

        with self.cr.savepoint(), patch.object(
                type(self.env['printnode.printer']),
                'printnode_print',
        ) as mock_printnode_printer:
            stock_picking._scenario_print_document_on_picking_status_change(
                report_id=self.so_report,
                printer_id=self.printer,
                number_of_copies=1,
                packages_to_print=stock_picking
            )
            mock_printnode_printer.assert_called_once_with(
                self.so_report,
                stock_picking,
                copies=1,
                options={},
            )

    def test_scenario_print_packages_label_on_transfer(self):
        """
        Test _scenario_print_packages_label_on_transfer method
        """

        self.test_stock_picking.move_line_ids.update({
            'result_package_id': self.package.id,
        })

        with self.cr.savepoint(), patch.object(
                type(self.env['printnode.printer']),
                'printnode_print',
        ) as mock_printnode_printer:
            self.test_stock_picking._scenario_print_packages_label_on_transfer(
                report_id=self.so_report,
                printer_id=self.printer,
                number_of_copies=1,
            )
            mock_printnode_printer.assert_called_once_with(
                self.so_report,
                self.package,
                copies=1,
                options={},
            )
