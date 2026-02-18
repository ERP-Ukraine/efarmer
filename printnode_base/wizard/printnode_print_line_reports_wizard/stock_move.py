# Copyright 2023 VentorTech OU
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class PrintnodePrintStockMoveReportsWizard(models.TransientModel):
    _name = 'printnode.print.stock.move.reports.wizard'
    _inherit = 'printnode.abstract.print.line.reports.wizard'
    _description = 'Print stock.move / stock.move.line Reports Wizard'

    # This field is used to determine which model to use in this wizard. If "Detailed Operations"
    # is checked, then we use stock.move.line model, otherwise stock.move (can be changed on UI)
    show_operations = fields.Boolean(
        string='Use Detailed Operations',
        default=lambda self: self._default_show_operations(),
    )

    report_id = fields.Many2one(
        comodel_name='ir.actions.report',
        domain='[("id", "in", report_ids)]',
        string='Report',
    )

    # Technical field to update report_id field on UI if user changes show_operations field
    report_ids = fields.Many2many(
        comodel_name='ir.actions.report',
        compute='_compute_report_ids',
        string='Reports',
    )

    stock_move_record_line_ids = fields.One2many(
        comodel_name='printnode.print.stock.move.reports.wizard.line',
        inverse_name='wizard_id',
        string='Records: Operations',
        default=lambda self: self._default_stock_move_record_line_ids(),
    )

    stock_move_line_record_line_ids = fields.One2many(
        comodel_name='printnode.print.stock.move.line.reports.wizard.line',
        inverse_name='wizard_id',
        string='Records: Detailed Operations',
        default=lambda self: self._default_stock_move_line_record_line_ids(),
    )

    def _default_record_line_ids(self):
        """
        Override this method to avoid NotImplementedError. We don't need this field in this wizard
        """
        return []

    def _default_show_operations(self):
        picking_id = self.env['stock.picking'].browse(self.env.context.get('active_id'))
        return picking_id.show_operations

    def _default_stock_move_record_line_ids(self):
        picking_id = self.env['stock.picking'].browse(self.env.context.get('active_id'))

        record_ids = picking_id.move_ids_without_package

        return [
            (0, 0, {
                'record_id': rec.id,
                'name': rec.product_id.name,
                'quantity': rec.quantity
            })
            for rec in record_ids
        ]

    def _default_stock_move_line_record_line_ids(self):
        picking_id = self.env['stock.picking'].browse(self.env.context.get('active_id'))

        record_ids = picking_id.move_line_ids_without_package

        return [
            (0, 0, {
                'record_id': rec.id,
                'name': rec.product_id.name,
                'quantity': rec.quantity
            })
            for rec in record_ids
        ]

    @api.depends('show_operations')
    def _compute_report_ids(self):
        for rec in self:
            model = 'stock.move.line' if rec.show_operations else 'stock.move'

            rec.report_ids = self.env['ir.actions.report'].search([
                ('model', '=', model),
                ('report_type', 'in', ['qweb-pdf', 'qweb-text', 'py3o']),
            ])

    @api.onchange('show_operations')
    def _onchange_show_operations(self):
        """
        This method is used to update report_id field on UI if user changes show_operations field
        """
        self.report_id = self.report_ids and self.report_ids[0] or None

    def _get_lines(self):
        """
        Wrapped in method to avoid overriding in child models
        """
        self.ensure_one()

        if self.show_operations:
            return self.stock_move_line_record_line_ids

        return self.stock_move_record_line_ids

    def _get_line_model(self):
        if self.show_operations:
            return self.env['stock.move.line']

        return self.env['stock.move']


class PrintnodePrintStockMoveReportsWizardLine(models.TransientModel):
    _name = 'printnode.print.stock.move.reports.wizard.line'
    _inherit = 'printnode.abstract.print.line.reports.wizard.line'
    _description = 'Record Line: stock.move'

    wizard_id = fields.Many2one(
        comodel_name='printnode.print.stock.move.reports.wizard',
    )

    record_id = fields.Many2one(
        comodel_name='stock.move',
    )

    name = fields.Char(
        string='Name',
        related='record_id.product_id.name',
    )


class PrintnodePrintStockMoveLineReportsWizardLine(models.TransientModel):
    _name = 'printnode.print.stock.move.line.reports.wizard.line'
    _inherit = 'printnode.abstract.print.line.reports.wizard.line'
    _description = 'Record Line: stock.move.line'

    wizard_id = fields.Many2one(
        comodel_name='printnode.print.stock.move.reports.wizard',
    )

    record_id = fields.Many2one(
        comodel_name='stock.move.line',
    )

    name = fields.Char(
        string='Name',
        related='record_id.product_id.name',
    )

    package_id = fields.Many2one(
        comodel_name='stock.package',
        related='record_id.package_id',
    )

    result_package_id = fields.Many2one(
        comodel_name='stock.package',
        related='record_id.result_package_id',
    )

    lot_id = fields.Many2one(
        comodel_name='stock.lot',
        related='record_id.lot_id',
    )
