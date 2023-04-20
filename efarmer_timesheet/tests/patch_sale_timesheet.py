# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).


from odoo.tests import tagged
from odoo.addons.sale_timesheet.tests.test_project_update import TestProjectUpdateSaleTimesheet


@tagged('post_install', '-at_install')
class TestProjectUpdateSaleTimesheetPatch(TestProjectUpdateSaleTimesheet):
    """
    Need for patching:
        - Odoo test_project_update_description_profitability() is expected to be run
        on a non-empty database and Demo Company can have currency EUR.
        Basic test fails if the company has specified currency other than USD.
    """

    def test_project_update_description_profitability(self):
        self.project_pigs.allow_billable = True
        currency_res_dict = {'EUR': '0.00\xa0€', 'USD': '$\xa00.00'}
        currency_expected_value = currency_res_dict.get(self.env.company.currency_id.name, 'EUR')
        template_values = self.env['project.update']._get_template_values(self.project_pigs)

        self.assertEqual(
            template_values['profitability']['costs'],
            currency_expected_value,
            'Project costs used in the template should be well defined'
        )
        self.assertEqual(
            template_values['profitability']['revenues'],
            currency_expected_value,
            'Project revenues used in the template should be well defined'
        )
        self.assertEqual(
            template_values['profitability']['margin'],
            0,
            'Margin used in the template should be well defined'
        )
        self.assertEqual(
            template_values['profitability']['margin_formatted'],
            currency_expected_value,
            'Margin formatted used in the template should be well defined'
        )
        self.assertEqual(
            template_values['profitability']['margin_percentage'],
            '0',
            'Margin percentage used in the template should be well defined'
        )


TestProjectUpdateSaleTimesheet.test_project_update_description_profitability = \
    TestProjectUpdateSaleTimesheetPatch.test_project_update_description_profitability
