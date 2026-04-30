# Copyright 2021 VentorTech OU
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    autoprint_paperformat_id = fields.Many2one(
        comodel_name='printnode.paper',
        string='Autoprint Paper Format',
        help=(
            'This settings defines which paper format '
            'should be chosen for printing labels of this carrier.'
        ),
    )

    exclude_invoice_printing = fields.Boolean(
        string='Exclude Invoice Printing',
        help=(
            'If this option is enabled, the invoice will not be printed automatically after '
            'the delivery order is validated. Ensure that a keyword is set in the "Exclusion Marker" '
            'field, which should be present in the invoice name to exclude it from printing.'
        ),
    )

    exclusion_marker = fields.Char(
        string='Exclusion Marker',
        help='Enter a text marker to identify invoices that should be excluded from printing.',
    )

    printer_id = fields.Many2one(
        comodel_name='printnode.printer',
        string='Printer',
    )

    printer_bin = fields.Many2one(
        comodel_name='printnode.printer.bin',
        string='Printer Bin',
        required=False,
        domain='[("printer_id", "=", printer_id)]',
    )

    @api.onchange('printer_id')
    def _onchange_printer(self):
        """
        Reset printer_bin field to avoid bug with printing
        in wrong bin
        """
        self.printer_bin = self.printer_id.default_printer_bin.id
