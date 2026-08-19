# Copyright 2021 VentorTech OU
# See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.tools import LazyTranslate

_lt = LazyTranslate(__name__)


PRINT_RULE_DESCRIPTION_DEPENDENCIES = [
    'user_id',
    'user_id.name',
    'report_id',
    'report_id.name',
    'workstation_id',
    'workstation_id.name',
    'printer_id',
    'printer_id.name',
    'printer_id.computer_id',
    'printer_id.computer_id.name',
    'printer_bin',
    'printer_bin.name',
    'exclude_from_auto_printing',
]

PRINT_RULE_CONDITION_TEMPLATES = {
    ('user', 'report', 'workstation'): _lt('When %(user)s prints %(report)s from %(workstation)s'),
    ('user', 'report'): _lt('When %(user)s prints %(report)s'),
    ('user', 'workstation'): _lt('When %(user)s prints any report from %(workstation)s'),
    ('report', 'workstation'): _lt('When %(report)s is printed from %(workstation)s'),
    ('user',): _lt('When %(user)s prints any report'),
    ('report',): _lt('When %(report)s is printed'),
    ('workstation',): _lt('When any report is printed from %(workstation)s'),
}

PRINT_RULE_DESCRIPTION_TEMPLATE = _lt('%(condition)s, %(action)s')
PRINT_RULE_NO_CONDITION_MESSAGE = _lt('Select at least one condition (User, Report, or Workstation)')
PRINT_RULE_NO_PRINTER_MESSAGE = _lt('Select a printer to complete this rule')
PRINT_RULE_DOWNLOAD_ACTION = _lt('it will be downloaded instead of printed')
PRINT_RULE_PRINTER_ACTION = _lt('it will be sent to %(printer)s printer (%(computer)s)')
PRINT_RULE_PRINTER_BIN_ACTION = _lt('it will be sent to %(printer)s printer (%(computer)s) using bin %(printer_bin)s')


class PrintNodePrintRuleMixin(models.AbstractModel):
    """Mixin for generating print rule descriptions.
    """
    _name = 'printnode.print.rule.mixin'
    _description = 'Print Rule Mixin'

    def _get_print_rule_description(self):
        """Return a user-friendly description that
           explains what the rule does.
        """
        self.ensure_one()

        condition = self._get_print_rule_condition_description()
        if not condition:
            return str(PRINT_RULE_NO_CONDITION_MESSAGE)

        return str(PRINT_RULE_DESCRIPTION_TEMPLATE) % {
            'condition': condition,
            'action': self._get_print_rule_action_description(),
        }

    def _get_print_rule_condition_description(self):
        """Return a user-friendly description of the rule conditions.
        """
        self.ensure_one()

        condition_key = self._get_print_rule_condition_key()
        if not condition_key:
            return False

        return str(PRINT_RULE_CONDITION_TEMPLATES[condition_key]) % {
            'user': self.user_id.name,
            'report': self.report_id.name,
            'workstation': self.workstation_id.name,
        }

    def _get_print_rule_condition_key(self):
        """Return selected rule condition names.
        """
        self.ensure_one()

        condition_key = []

        if self.user_id:
            condition_key.append('user')
        if self.report_id:
            condition_key.append('report')
        if self.workstation_id:
            condition_key.append('workstation')

        return tuple(condition_key)

    def _get_print_rule_action_description(self):
        """Return a user-friendly description of the rule action.
        """
        self.ensure_one()

        if self.exclude_from_auto_printing:
            return str(PRINT_RULE_DOWNLOAD_ACTION)

        if self.printer_bin:
            return str(PRINT_RULE_PRINTER_BIN_ACTION) % {
                'printer': self.printer_id.name,
                'computer': self.printer_id.computer_id.name,
                'printer_bin': self.printer_bin.name,
            }

        return str(PRINT_RULE_PRINTER_ACTION) % {
            'printer': self.printer_id.name,
            'computer': self.printer_id.computer_id.name,
        }
