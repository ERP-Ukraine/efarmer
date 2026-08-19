# Copyright 2021 VentorTech OU
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

from .printnode_print_rule_mixin import PRINT_RULE_DESCRIPTION_DEPENDENCIES


class PrintNodePrintRule(models.Model):
    """
    Print Rules Model
    """
    _name = 'printnode.print.rule'
    _inherit = ['printnode.print.rule.mixin']
    _description = 'Print Rules'
    _order = 'sequence asc, id asc'

    active = fields.Boolean(
        'Active',
        default=True,
        help='Activate or Deactivate the rule.'
    )

    description = fields.Char(
        string='Description',
        compute='_compute_description',
        help='Automatically generated rule description.',
    )

    exclude_from_auto_printing = fields.Boolean(
        'Exclude from Auto-Printing',
        default=False,
        help="""If you would like to exclude this report from auto-printing,
                select this checkbox."""
    )

    printer_id = fields.Many2one(
        'printnode.printer',
        string='Printer',
        ondelete='set null',
    )

    printer_bin = fields.Many2one(
        'printnode.printer.bin',
        string='Printer Bin',
        required=False,
        domain='[("printer_id", "=", printer_id)]',
    )

    report_paper_id = fields.Many2one(
        'printnode.paper',
        string='Report Paper'
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

    report_type = fields.Selection(
        related='report_id.report_type',
        readonly=True,
    )

    sequence = fields.Integer(
        string='Sequence',
        default=1,
    )

    user_id = fields.Many2one(
        'res.users',
        string='User',
    )

    workstation_id = fields.Many2one(
        'printnode.workstation',
        string='Workstation',
    )

    @api.constrains('user_id', 'report_id', 'workstation_id')
    def _check_duplicate_conditions(self):
        for rule in self:
            domain = [
                ('id', '!=', rule.id),
                ('user_id', '=', rule.user_id.id or False),
                ('report_id', '=', rule.report_id.id or False),
                ('workstation_id', '=', rule.workstation_id.id or False),
            ]

            if self.with_context(active_test=False).search_count(domain):
                raise ValidationError(_(
                    'A rule with the same conditions already exists, including archived rules. '
                    'Please update the existing rule or change the conditions.'
                ))

    @api.depends(*PRINT_RULE_DESCRIPTION_DEPENDENCIES)
    def _compute_description(self):
        for rule in self:
            rule.description = rule._get_print_rule_description()

    def action_open_print_rule_wizard(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': _('Edit Print Rule'),
            'res_model': 'printnode.print.rule.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref(
                'printnode_base.printnode_print_rule_wizard_form'
            ).id,
            'target': 'new',
            'context': {
                'form_view_initial_mode': 'edit',
                'default_print_rule_id': self.id,
                'default_user_id': self.user_id.id,
                'default_report_id': self.report_id.id,
                'default_workstation_id': self.workstation_id.id,
                'default_printer_id': self.printer_id.id,
                'default_printer_bin': self.printer_bin.id,
                'default_report_paper_id': self.report_paper_id.id,
                'default_exclude_from_auto_printing': self.exclude_from_auto_printing,
                'default_active': self.active,
            },
        }

    def action_delete_print_rule(self):
        """Delete the selected Print Rule."""
        self.ensure_one()
        self.unlink()

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
