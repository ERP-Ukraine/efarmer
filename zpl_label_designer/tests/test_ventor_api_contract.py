# Copyright 2026 VentorTech OU
# See LICENSE file for full copyright and licensing details.

import json

from odoo import http
from odoo.tests import tagged

from .common import TestZldCommon, TestZldHttpCommon


FIELDS = {
    # The app lists published labels of a model to offer them for printing
    'zld.label': {
        'name': {'type': 'char', 'required': True},
        'is_published': {'type': 'boolean'},
        'model_id': {'type': 'many2one', 'comodel': 'ir.model'},
    },
    # The app creates the label wizard with a ZPL Designer label and calls `process`
    'product.label.layout': {
        'print_format': {'type': 'selection', 'selection_keys': ['zld_label']},
        'zld_label_id': {'type': 'many2one', 'comodel': 'zld.label'},
    },
}


@tagged('post_install', '-at_install', 'zld_ventor_api')  # can be run by test-tag
class TestVentorApiContract(TestZldCommon):
    """
    Tests of the Ventor PRO API contract: fields and calls the mobile app uses directly.

    The app is released through app stores, so a rename here breaks installed apps before they
    can be updated. A failing test means the change needs the Ventor PRO team's agreement,
    not only a fix of the test.
    """

    def test_fields(self):
        """
        Test that the fields the app reads and writes keep their name, type and values
        """
        self._assert_fields_contract(FIELDS)

    def test_user_lists_published_labels(self):
        """
        Test that a warehouse user gets published labels with search_read and name_search
        """
        Label = self.env['zld.label'].with_user(self.user)

        with self._assert_contract('zld.label search_read'):
            labels = Label.search_read([('is_published', '=', True)], ['name', 'model_id', 'is_published'])
        with self._assert_contract('zld.label name_search'):
            found = Label.name_search(self.label.name)

        self.assertIn(
            self.label.id, [label['id'] for label in labels],
            self._contract_message('zld.label search_read', 'a published label is not returned'),
        )
        self.assertIn(
            self.label.id, [label_id for label_id, _name in found],
            self._contract_message('zld.label name_search', 'a published label is not found by name'),
        )

    def test_process_zld_label(self):
        """
        Test that the label wizard with a ZPL Designer label returns the report of that label
        """
        with self._assert_contract('product.label.layout.create'):
            wizard = self.env['product.label.layout'].with_user(self.user).create({
                'product_ids': [(6, 0, self.product_id.ids)],
                'print_format': 'zld_label',
                'zld_label_id': self.label.id,
            })
        with self._assert_contract('product.label.layout.process'):
            action = wizard.process()

        self._assert_contract_equal(
            action.get('type'), 'ir.actions.report',
            'product.label.layout.process', 'the returned action is not a report action')
        self._assert_contract_equal(
            action.get('report_name'), self.label.action_report_id.report_name,
            'product.label.layout.process', 'the returned action is not the report of the ZPL Designer label')


@tagged('post_install', '-at_install', 'zld_ventor_api')  # can be run by test-tag
class TestVentorApiContractReportDownload(TestZldHttpCommon):
    """
    Tests of the Ventor PRO API contract: /report/download, which this module overrides
    """

    def _download_label(self):
        """
        Download the test label the way the app does
        """
        self.authenticate(self.user.login, 'user_zld')

        report = self.label.action_report_id
        url = f'/report/text/{report.report_name}/{self.product_id.id}'

        # The app sends the same five values here as to /report/print:
        # report url, report type, printer, printer bin, source document
        return self.url_open('/report/download', data={
            'data': json.dumps([url, 'qweb-text', False, False, 'Ventor PRO']),
            'context': json.dumps({}),
            'token': 'dummy-because-api-expects-one',
            'csrf_token': http.Request.csrf_token(self),
        })

    def test_download_label_as_zpl(self):
        """
        Test that a label without PDF conversion is downloaded as ZPL
        """
        response = self._download_label()

        problem = 'a ZPL label is not downloaded as ZPL'
        self._assert_contract_equal(response.status_code, 200, '/report/download', problem)

        content_disposition = response.headers.get('Content-Disposition', '')
        self.assertIn('attachment', content_disposition, self._contract_message('/report/download', problem, [
            f'Content-Disposition now: {content_disposition!r}',
        ]))
        self.assertIn(b'^XA', response.content, self._contract_message('/report/download', problem, [
            f'Response body now: {response.content[:200]!r}',
        ]))

    def test_download_label_as_pdf(self):
        """
        Test that a label with PDF conversion is downloaded as PDF
        """
        self.label.convert_to_pdf = True

        generate_pdf = self._create_patch_object(
            type(self.env['ir.actions.report']), '_generate_pdf_from_zpl_label')
        generate_pdf.return_value = b'%PDF-1.4 label'

        response = self._download_label()

        problem = 'a label converted to PDF is not downloaded as PDF'
        self._assert_contract_equal(response.status_code, 200, '/report/download', problem)
        self._assert_contract_equal(
            response.headers.get('Content-Type'), 'application/pdf', '/report/download Content-Type', problem)
        self._assert_contract_equal(response.content, b'%PDF-1.4 label', '/report/download body', problem)
