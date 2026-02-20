# Copyright 2026 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).


import base64
from io import BytesIO
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from odoo.tests.common import TransactionCase
from odoo import fields


class TestHrPayslipImportWizard(TransactionCase):
    def setUp(self):
        super().setUp()
        self.base_date = fields.Date.today()

        self.employee_1 = self.env['hr.employee'].create({
            'name': 'John',
        })
        self.employee_2 = self.env['hr.employee'].create({
            'name': 'Jane',
        })

        self.input_type_1 = self.env['hr.payslip.input.type'].create({
            'name': 'Bonus',
            'code': 'BNS',
        })
        self.input_type_2 = self.env['hr.payslip.input.type'].create({
            'name': 'Deduction',
            'code': 'DED',
        })
        versions = self.employee_1.version_ids.sorted('date_version')

        current_versions = versions.filtered(lambda v: v.is_current)

        if current_versions:
            self.contract_1 = current_versions[0]
        else:
            # fallback: latest version
            if versions:
                self.contract_1 = versions[-1]
            else:
                self.contract_1 = self.env['hr.version'].create({
                    'name': 'Current Version',
                    'employee_id': self.employee_1.id,
                    'wage': 2000,
                    'date_version': self.base_date,
                    'date_generated_from': self.base_date,
                    # 'structure_type_id': self.structure_type.id,
                })

        self.binary_data = b'VGhpcyBpcyBhIHRlc3QgYmluYXJ5IGZpbGUuCg=='
        self.wizard = self._create_import_wizard(self.binary_data)

    def _create_import_wizard(self, data):
        return self.env['hr.payslip.import.wizard'].create({
            'import_file': base64.b64encode(data),
        })

    def _create_payroll_batch(self, batch_date_start, batch_date_end):
        batch = self.env['hr.payslip.run'].create({
            'name': 'From {} to {}'.format(
                batch_date_start.strftime('%d/%m/%Y'),
                batch_date_end.strftime('%d/%m/%Y'),
            ),
            'date_start': batch_date_start,
            'date_end': batch_date_end,
        })
        return batch

    def test_wizard_values(self):
        batch_date_start = (datetime.now() + relativedelta(days=-3)).date()
        batch_date_end = (datetime.now() + relativedelta(days=-2)).date()
        self._create_payroll_batch(batch_date_start, batch_date_end)

        expected_date_from = date.today().replace(day=1)
        expected_date_to = (datetime.now() + relativedelta(months=+1, day=1, days=-1)).date()

        self.assertEqual(self.wizard.date_from, expected_date_from)
        self.assertEqual(self.wizard.date_to, expected_date_to)
        self.assertEqual(
            self.wizard.last_period,
            '{} - {}'.format(
                batch_date_start.strftime('%d/%m/%Y'),
                batch_date_end.strftime('%d/%m/%Y'),
            )
        )

    def test_decode_file(self):
        expected_result = BytesIO(b'This is a test binary file.\n')
        result = self.wizard._decode_file(self.binary_data)
        self.assertEqual(result.getvalue(), expected_result.getvalue())

    def test_get_existing_data(self):
        employee_import_data = [self.employee_1.name, '', 'Test Name']
        existing_employee = self.wizard._get_existing_data('hr.employee', employee_import_data, 'Employee')
        self.assertEqual(existing_employee, self.employee_1)
        self.assertEqual(
            self.wizard.alert,
            'File contains empty values in the Employee data!\n'
            'Employees with the following names were not found in the system: \nTest Name\n'
        )

    def test_create_payslip(self):
        payslip_vals = [
            {self.employee_1: [(self.input_type_1.id, 0.0), (self.input_type_2.id, 10.0)]},
            {self.employee_2: [(self.input_type_1.id, 20.0), (self.input_type_2.id, 30.0)]},
        ]

        self.wizard.create_payslip(payslip_vals)

        payslips = self.env['hr.payslip'].search([])
        batch = self.env['hr.payslip.run'].search([])

        self.assertEqual(len(payslips), 2)

        payslip_1 = payslips.filtered(lambda p: p.employee_id == self.employee_1)
        payslip_2 = payslips.filtered(lambda p: p.employee_id == self.employee_2)

        self.assertTrue(all([payslip_1, payslip_2]))

        self.assertEqual(payslip_1.version_id, self.contract_1)

        self.assertEqual(payslip_1.date_from, self.wizard.date_from)
        self.assertEqual(payslip_1.date_to, self.wizard.date_to)
        self.assertEqual(payslip_1.payslip_run_id, batch)

        payslip_1_input_lines = payslip_1.mapped('input_line_ids')
        self.assertEqual(len(payslip_1_input_lines), 1)
        self.assertEqual(payslip_1_input_lines[0].input_type_id, self.input_type_2)
        self.assertEqual(payslip_1_input_lines[0].amount, 10)

        payslip_2_input_lines = payslip_2.mapped('input_line_ids')
        self.assertEqual(len(payslip_2_input_lines), 2)
        lines_expected_vals = [(line.input_type_id.id, line.amount)
            for line in payslip_2_input_lines]
        self.assertEqual(
            set(lines_expected_vals),
            set([(self.input_type_2.id, 30.0), (self.input_type_1.id, 20.0)])
        )
