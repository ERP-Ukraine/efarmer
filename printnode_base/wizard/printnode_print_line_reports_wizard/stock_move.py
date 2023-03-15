# Copyright 2023 VentorTech OU
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class PrintnodePrintStockMoveReportsWizard(models.TransientModel):
    _name = 'printnode.print.stock.move.reports.wizard'
    _inherit = 'printnode.abstract.print.line.reports.wizard'
    _description = 'Print stock.move Reports Wizard'

    quantity = fields.Selection(
        selection_add=[
            ('demand', 'Based on demand'),
            ('done', 'Based on done quantity'),
        ],
        ondelete={'demand': 'set default', 'done': 'set default'},
    )

    record_line_ids = fields.One2many(
        comodel_name='printnode.print.stock.move.reports.wizard.line',
        inverse_name='wizard_id',
        string='Records',
        default=lambda self: self._default_record_line_ids(),
    )

    def _get_report_domain(self):
        return [
            ('model', '=', 'stock.move'),
            ('report_type', 'in', ['qweb-pdf', 'qweb-text', 'py3o']),
        ]

    @api.onchange('quantity')
    def _change_quantity(self):
        for record in self.record_line_ids:
            if self.quantity == 'demand':
                record.quantity = record.record_id.product_uom_qty
            elif self.quantity == 'done':
                record.quantity = record.record_id.quantity_done
            else:
                record.quantity = 1

    def _default_record_line_ids(self):
        picking_id = self.env['stock.picking'].browse(self.env.context.get('active_id'))

        record_ids = picking_id.move_ids_without_package

        return [(0, 0, {'record_id': rec.id, 'name': rec.product_id.name}) for rec in record_ids]

    def _get_line_model(self):
        return self.env['stock.move']


class PrintnodePrintStockMoveReportsWizardLine(models.TransientModel):
    _name = 'printnode.print.stock.move.reports.wizard.line'
    _inherit = 'printnode.abstract.print.line.reports.wizard.line'
    _description = 'Record Line'

    record_id = fields.Many2one(
        comodel_name='stock.move',
    )

    name = fields.Char(
        string='Name',
        related='record_id.product_id.name',
    )

    wizard_id = fields.Many2one(
        comodel_name='printnode.print.stock.move.reports.wizard',
    )
