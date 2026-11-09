# Copyright 2026 VentorTech OU
# See LICENSE file for full copyright and licensing details.

from odoo.service.model import call_kw
from odoo.tests import tagged

from odoo.addons.zpl_label_designer.tests.common import TestZldCommon


FIELDS = {
    # The app matches 'zld_label' literally to show ZPL Designer labels for fast printing
    'res.company': {
        'print_labels_format': {'type': 'selection', 'selection_keys': ['zld_label']},
    },
    'res.config.settings': {
        'print_labels_format': {
            'type': 'selection',
            'related': 'company_id.print_labels_format',
            'selection_keys': ['zld_label'],
        },
    },
}


@tagged('post_install', '-at_install', 'zld_ventor_api')  # can be run by test-tag
class TestVentorApiContract(TestZldCommon):
    """
    Tests of the Ventor PRO API contract: fields and calls the mobile app uses directly.

    A failing test means the change needs the Ventor PRO team's agreement,
    not only a fix of the test.
    """

    def test_fields(self):
        """
        Test that the fields the app reads keep their name, type and values
        """
        self._assert_fields_contract(FIELDS)

    def test_user_reads_label_format_from_settings(self):
        """
        Test that a warehouse user reads the company label format from the settings
        """
        with self._assert_contract("res.company.print_labels_format = 'zld_label'"):
            self.company.print_labels_format = 'zld_label'

        # The exact call the app makes: read of a transient record that does not exist
        with self._assert_contract("res.config.settings.read([0], ['print_labels_format'])"):
            values = call_kw(
                self.env['res.config.settings'].with_user(self.user), 'read', [[0], ['print_labels_format']], {})

        self._assert_contract_equal(
            values[0].get('print_labels_format'), 'zld_label',
            "res.config.settings.read([0], ['print_labels_format'])",
            'a warehouse user does not get the company label format',
        )
