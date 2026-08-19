# Copyright 2021 VentorTech OU
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api
from odoo.exceptions import ValidationError

from ..models.printnode_print_rule_mixin import (
    PRINT_RULE_DESCRIPTION_DEPENDENCIES,
    PRINT_RULE_NO_CONDITION_MESSAGE,
    PRINT_RULE_NO_PRINTER_MESSAGE,
)


class PrintNodePrintRuleWizard(models.TransientModel):
    _name = 'printnode.print.rule.wizard'
    _inherit = 'printnode.print.rule.mixin'
    _description = 'Print Rule Wizard'

    active = fields.Boolean(
        string='Active',
        default=True,
    )

    print_rule_id = fields.Many2one(
        'printnode.print.rule',
        string='Print Rule',
        readonly=True,
    )

    user_id = fields.Many2one(
        'res.users',
        string='User',
    )

    report_id = fields.Many2one(
        'ir.actions.report',
        string='Report',
        domain="[('report_type', 'in', ('qweb-pdf', 'qweb-text', 'py3o'))]",
    )

    report_model = fields.Char(
        related='report_id.model',
        readonly=True,
    )

    workstation_id = fields.Many2one(
        'printnode.workstation',
        string='Workstation',
    )

    printer_id = fields.Many2one(
        'printnode.printer',
        string='Printer',
    )

    printer_bin = fields.Many2one(
        'printnode.printer.bin',
        string='Printer Bin',
        domain='[("printer_id", "=", printer_id)]',
    )

    report_paper_id = fields.Many2one(
        'printnode.paper',
        string='Report Paper',
    )

    exclude_from_auto_printing = fields.Boolean(
        string='Exclude from Auto-Printing',
    )

    preview = fields.Char(
        string='Rule Preview',
        compute='_compute_preview',
    )

    preview_state = fields.Selection(
        [
            ('warning', 'Warning'),
            ('success', 'Success'),
        ],
        compute='_compute_preview',
    )

    @api.depends(*PRINT_RULE_DESCRIPTION_DEPENDENCIES)
    def _compute_preview(self):
        """Update the preview message and its visual state in the wizard.
        """
        for wizard in self:
            has_condition = bool(
                wizard.user_id
                or wizard.report_id
                or wizard.workstation_id
            )

            if not has_condition:
                wizard.preview = str(PRINT_RULE_NO_CONDITION_MESSAGE)
                wizard.preview_state = 'warning'
                continue

            if not wizard.exclude_from_auto_printing and not wizard.printer_id:
                wizard.preview = str(PRINT_RULE_NO_PRINTER_MESSAGE)
                wizard.preview_state = 'warning'
                continue

            wizard.preview = wizard._get_print_rule_description()
            wizard.preview_state = 'success'

    @api.onchange('exclude_from_auto_printing', 'printer_id')
    def _onchange_printer(self):
        """Keep printer bin values consistent with the selected printer action.
        """
        if self.exclude_from_auto_printing:
            self.printer_id = False
            self.printer_bin = False
        elif not self.printer_id:
            self.printer_bin = False
        elif self.printer_id.default_printer_bin:
            self.printer_bin = self.printer_id.default_printer_bin.id

    def _check_rule_values(self):
        """Validate required rule conditions before saving the rule.
        """
        self.ensure_one()

        if not (self.user_id or self.report_id or self.workstation_id):
            raise ValidationError(str(PRINT_RULE_NO_CONDITION_MESSAGE))

        if not self.printer_id and not self.exclude_from_auto_printing:
            raise ValidationError(str(PRINT_RULE_NO_PRINTER_MESSAGE))

    def _prepare_print_rule_values(self):
        """Prepare values used to create or update the Print Rule.
        """
        self.ensure_one()

        return {
            'user_id': self.user_id.id,
            'report_id': self.report_id.id,
            'workstation_id': self.workstation_id.id,
            'printer_id': self.printer_id.id if not self.exclude_from_auto_printing else False,
            'printer_bin': self.printer_bin.id if not self.exclude_from_auto_printing else False,
            'report_paper_id': self.report_paper_id.id,
            'exclude_from_auto_printing': self.exclude_from_auto_printing,
            'active': self.active,
        }

    def action_save(self):
        """Create a new Print Rule or update the selected one.
        """
        self.ensure_one()
        self._check_rule_values()

        values = self._prepare_print_rule_values()

        if self.print_rule_id:
            self.print_rule_id.write(values)
        else:
            self.env['printnode.print.rule'].create(values)

        return {'type': 'ir.actions.act_window_close'}
