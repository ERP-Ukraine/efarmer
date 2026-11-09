# Copyright 2026 VentorTech OU
# See LICENSE file for full copyright and licensing details.

import ast
import json
from unittest.mock import MagicMock, patch

from werkzeug.exceptions import Unauthorized

from odoo import http
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import new_test_user
from odoo.tools import mute_logger

from odoo.addons.zpl_label_designer.controllers import utils as controller_utils
from odoo.addons.zpl_label_designer.models import ir_actions_report

from .common import TestZldCommon, TestZldHttpCommon


# What the portal generates: a nested label, its offsets and a barcode with a calculated offset
PORTAL_TEMPLATE = """
<t t-name="zld-label-name">
    <t t-foreach="docs" t-as="doc">
        ^XA
        <t t-set="seller_ids_line_height" t-value="40"/>
        <t t-set="seller_ids_margin" t-value="0"/>
        <t t-foreach="doc.seller_ids" t-as="doc_seller_ids_line">
            ^FO10,<t t-out="seller_ids_margin + 20"/>^FD<t t-out="doc_seller_ids_line.price"/>^FS
            <t t-set="seller_ids_margin" t-value="seller_ids_margin + seller_ids_line_height"/>
        </t>
        <t t-set="zld_barcode_value"><t t-out="doc.barcode"/></t>
        <t t-set="zld_barcode_offset" t-value="zld_label.get_barcode_offset(
            text=zld_barcode_value, width=300, align='center', barcode_size=3)"/>
        ^FO<t t-out="zld_barcode_offset + 10"/>,50^BC^FD<t t-out="zld_barcode_value"/>^FS
        ^FD<t t-out="doc.create_date.strftime('%d.%m.%Y')"/>^FS
        ^FD<t t-out="time.strftime('%m/%d/%Y') if doc.display_name else ''"/>^FS
        ^FD<t t-esc="'{:.2f}'.format(doc.list_price or 0) + ' kg'"/>^FS
        ^XZ
    </t>
</t>
"""


@tagged('post_install', '-at_install', 'zld_security')  # can be run by test-tag
class TestZldSecurity(TestZldCommon):
    """
    Tests of what users without administrator rights and label expressions can reach
    """

    @classmethod
    def setUpClass(cls):
        super(TestZldSecurity, cls).setUpClass()

        cls.Label = cls.env['zld.label']
        cls.Settings = cls.env['res.config.settings']
        cls.admin = cls.env.ref('base.user_admin')
        cls.portal_user = new_test_user(cls.env, login='zld_portal', groups='base.group_portal')
        cls.users = cls.portal_user | cls.user

    def test_designer_api_methods_are_private(self):
        """
        Test that the methods behind the designer API can't be called over RPC: Odoo refuses private ones
        """
        for method in ['get_preview_data', 'create_label', 'update_label', 'delete_label']:
            with self.subTest(method=method):
                self.assertFalse(hasattr(self.Label, method))
                self.assertTrue(hasattr(self.Label, '_' + method))

    def test_only_administrator_gets_api_key(self):
        """
        Test that the API key is given to an administrator and to no one else
        """
        key = self.Settings.get_zld_api_key()
        self.assertTrue(key)
        self.assertEqual(self.Settings.with_user(self.admin).get_zld_api_key(), key)
        self.assertEqual(self.Settings.with_user(self.admin).new({}).zld_api_key, key)

        for user in self.users:
            with self.subTest(user=user.login):
                settings = self.Settings.with_user(user)
                self.assertFalse(settings.get_zld_api_key())
                self.assertFalse(settings.new({}).zld_api_key)
                self.assertNotIn(key, settings.open_designer_connection()['url'])

    def test_only_administrator_updates_api_key(self):
        """
        Test that users can't replace the API key
        """
        key = self.Settings.get_zld_api_key()

        for user in self.users:
            with self.subTest(user=user.login):
                with self.assertRaises(AccessError):
                    self.Settings.with_user(user).generate_zld_api_key()

        self.assertEqual(self.Settings.get_zld_api_key(), key)

        self.Settings.with_user(self.admin).generate_zld_api_key()
        self.assertNotEqual(self.Settings.get_zld_api_key(), key)

    def test_forbidden_formulas_are_rejected(self):
        """
        Test that formulas can't reach other models, SQL, other rights and writes at any depth
        """
        for formula in [
            'doc.categ_id.env.user.name',
            "doc.categ_id.env['res.users'].search([]).ids",
            'doc.categ_id.sudo().name',
            'doc.categ_id.with_user(1).name',
            'doc.categ_id.env.cr.dbname',
            'doc.categ_id._cr.dbname',
            'doc.categ_id.pool',
            "doc.categ_id.write({'name': 'x'})",
            "doc.categ_id.create({'name': 'x'})",
            'doc.categ_id.unlink()',
            "doc.name and env['res.users']",
            'doc.name and request.env',
            "f'{doc.categ_id.env}'",
            "'{0.env}'.format(doc.categ_id)",
            "'{0[0].env}'.format([doc.categ_id])",
            "'{:{0.env}}'.format(doc.categ_id)",
            "('{0.' + 'env}').format(doc.categ_id)",
            "str.format('{0.env}', doc.categ_id)",
            "'{a.env}'.format_map({'a': doc.categ_id})",
        ]:
            for fields in [
                {'FORMULA:' + formula: None},
                {'categ_id': {'FORMULA:' + formula.replace('doc.categ_id', 'doc.parent_id'): None}},
            ]:
                with self.subTest(fields=fields):
                    with self.assertRaisesRegex(UserError, "can't use"):
                        self.Label._validate_label_fields('product.product', fields)

    def test_formulas_that_read_and_format_are_accepted(self):
        """
        Test that documented formulas and formulas used by customers stay valid
        """
        for formula in [
            "(doc.name or '').upper()",
            "(doc.default_code or '') + ' / ' + (doc.name or '')",
            "'{:.1f}'.format(doc.list_price or 0)",
            "'$ ' + '{:.2f}'.format(doc.list_price or 0)",
            "'{:,.2f}'.format(doc.list_price or 0)",
            "doc.create_date.strftime('%d.%m.%Y %H:%M')",
            "doc.barcode or 'NO BARCODE'",
            "(doc.name or '')[:20]",
            "str(int((doc.weight or 0) * 1000)) + ' g'",
            "'HEAVY' if (doc.weight or 0) > 1 else 'LIGHT'",
            "', '.join(doc.seller_ids.mapped('product_name'))",
            "doc.create_date.strftime('%m/%d/%Y') if doc.create_date else ''",
            "time.strftime('%m/%d/%Y') if doc.display_name else ''",
            "'%d items' % len(doc.seller_ids)",
            "doc._get_attribute('Test Diameter')",
            "doc.write_date",
        ]:
            with self.subTest(formula=formula):
                self.Label._validate_label_fields('product.product', {'FORMULA:' + formula: None})

    def test_formula_support_is_checked_at_any_depth(self):
        """
        Test that disabled formula support also applies to formulas of related records
        """
        self.company.enable_formulas = False

        for fields in [
            {'FORMULA:doc.name': None},
            {'categ_id': {'FORMULA:doc.name': None}},
            {'seller_ids': [{'partner_id': {'FORMULA:doc.name': None}}]},
        ]:
            with self.subTest(fields=fields):
                with self.assertRaisesRegex(UserError, 'formula support is currently disabled'):
                    self.Label._check_formula_support(fields)

        self.Label._check_formula_support({'categ_id': {'name': None}, 'seller_ids': [{'price': None}]})

        self.company.enable_formulas = True
        self.Label._check_formula_support({'categ_id': {'FORMULA:doc.name': None}})

    def test_template_expressions_are_checked(self):
        """
        Test that a template can't do what a formula can't
        """
        for directive in [
            '<t t-out="doc.env.user.name"/>',
            '<t t-esc="env[\'res.users\'].search([])"/>',
            '<t t-if="doc.sudo()"/>',
            '<t t-foreach="doc.env[\'res.users\'].search([])" t-as="user"/>',
            '<t t-set="x" t-value="doc.env.cr"/>',
            '<a t-att-href="doc.env.cr"/>',
            '<a t-attf-href="/{{ doc.env.cr }}"/>',
            '<a t-attf-href="/#{ doc.env.cr }"/>',
            '<t t-set="x" t-valuef="{{ doc.env.cr }}"/>',
            '<t t-call="{{ doc.env.cr }}"/>',
        ]:
            with self.subTest(directive=directive):
                with self.assertRaisesRegex(UserError, "can't use"):
                    self.Label._check_template_expressions('<t>%s</t>' % directive)

    def test_template_directives_are_limited(self):
        """
        Test that a template can only use known directives and that their values are read as QWeb reads them
        """
        for directive in [
            '<t t-call="web.layout"/>',
            '<t t-call="web.layout" x="doc.name"/>',
            '<t t-call.translate="web.layout"/>',
            '<t t-call-assets="web.assets_backend"/>',
            '<t t-cache="doc.id"/>',
            '<t t-lang="doc.lang"/>',
            '<t t-tag="doc.name"/>',
            '<t t-set="{\'x\': doc.env.cr}"/>',
            '<t t-set="x" t-valuef.translate="x #{doc.env.cr}"/>',
            '<a t-attf-title.translate="x #{doc.env.cr}"/>',
            '<a t-attf-title="{{ 1 &#10; #{doc.env.cr} }}"/>',
            '<t t-set="x" t-valuef="{{ 1 &#10; #{doc.env.cr} }}"/>',
        ]:
            with self.subTest(directive=directive):
                with self.assertRaisesRegex(UserError, "can't use"):
                    self.Label._check_template_expressions('<t>%s</t>' % directive)

        self.Label._check_template_expressions(
            '<t t-name="label-name"><t t-foreach="docs" t-as="doc">'
            '<t t-set="x" t-value="1"/><t t-set="y">text</t><t t-set="{\'z\': doc.name}"/>'
            '<t t-if="doc.name" t-out="x"/><t t-else="" t-esc="y"/>'
            '<t t-set="w" t-valuef.translate="text {{ doc.name }}"/>'
            '<a class="a b" title.translate="some text" t-att-href="doc.name" t-attf-title="x {{ doc.name }}"/>'
            '</t></t>'
        )

    def test_designer_api_sets_only_its_fields(self):
        """
        Test that the designer API changes the label fields it is meant to change and nothing else
        """
        attrs = {
            'name': 'Test API Fields',
            'model': 'product.product',
            'qweb_xml': PORTAL_TEMPLATE,
            'label_fields': {'name': None},
            'width': 2,
            'height': 1,
            'dpi': 203,
            'orientation': 'normal',
            'designer_label_id': 'test-api-fields',
        }
        other_view = self.env['ir.ui.view'].create({
            'name': 'Test Other View',
            'type': 'qweb',
            'key': 'zpl_label_designer.test_other_view',
            'arch': '<t t-name="zpl_label_designer.test_other_view"><div>Other</div></t>',
        })
        other_arch = other_view.arch
        unknown = {
            'view_id': other_view.id,
            'action_report_id': False,
            'is_published': False,
            'print_report_name': "'Other'",
        }

        label = self.Label.browse(self.Label._create_label(dict(attrs, **unknown)))
        view, report = label.view_id, label.action_report_id
        self.assertNotEqual(view, other_view)
        self.assertTrue(report)
        self.assertTrue(label.is_published)
        self.assertFalse(label.print_report_name)

        self.Label._update_label(label.id, dict(attrs, name='Test API Fields New', width=3, **unknown))
        self.assertEqual(label.name, 'Test API Fields New')
        self.assertEqual(label.width, 3)
        self.assertEqual(label.view_id, view)
        self.assertEqual(label.action_report_id, report)
        self.assertTrue(label.is_published)
        self.assertFalse(label.print_report_name)
        self.assertEqual(other_view.arch, other_arch)

    def test_template_gets_label_with_rights_of_the_user(self):
        """
        Test that a template gets the label with the rights of whoever prints it and can still calculate offsets
        """
        for user in self.users:
            with self.subTest(user=user.login):
                reports = self.env['ir.actions.report'].with_user(user)
                report = reports._get_report(self.label.action_report_id.id)
                self.assertTrue(report.env.su)

                label = reports._get_rendering_context(report, [self.product_id.id], {})['zld_label']
                self.assertEqual(label, self.label)
                self.assertFalse(label.env.su)
                self.assertEqual(label.env.uid, user.id)
                self.assertEqual(label.get_barcode_offset(text='12', width=300, align='end', barcode_size=1), 243)

    def test_report_name_preview_checks_the_expression(self):
        """
        Test that the preview evaluates only allowed expressions, and a value that is not allowed doesn't break the form
        """
        values = {'name': 'Test Preview', 'model_id': self.env.ref('product.model_product_product').id}
        label = self.Label.new(dict(values, print_report_name='object.sudo().name'))

        with patch('odoo.addons.zpl_label_designer.models.zld_label.safe_eval') as safe_eval:
            self.assertEqual(label.print_report_name_preview, 'Expression is not allowed')

            with self.assertRaises(ValidationError):
                label._onchange_print_report_name()

        safe_eval.assert_not_called()

        label = self.Label.new(dict(values, print_report_name="'Label ' + str(object.id)"))
        self.assertTrue(label.print_report_name_preview.startswith('Label '))
        label._onchange_print_report_name()

        self.assertEqual(self.Label.new(values).print_report_name_preview, 'Test Preview')

    def test_orm_methods_that_change_data_are_rejected(self):
        """
        Test that expressions can't call the ORM methods that change data, not only write and create
        """
        for expression in [
            "doc.update({'name': 'x'})",
            "doc.name_create('x')",
            'doc.load([], [])',
            'doc.action_archive()',
            'doc.action_unarchive()',
            'doc.toggle_active()',
            'doc.copy_translations(doc)',
            "doc.update_field_translations('name', {})",
            'doc.web_save({}, {})',
            'doc.web_save_multi([], {})',
            'doc.web_unlink()',
            'doc.web_resequence([])',
            'doc.web_override_translations({})',
        ]:
            with self.subTest(expression=expression):
                with self.assertRaisesRegex(UserError, "can't use"):
                    self.Label._check_expression(expression)

    def test_pdf_depends_on_rights_on_the_record(self):
        """
        Test that a user without rights on labels gets a PDF of a record they can read and not of another one
        """
        label = self.Label.browse(self.Label._create_label({
            'name': 'Test PDF Rights',
            'model': 'res.partner',
            'qweb_xml': '<t t-name="x"><t t-foreach="docs" t-as="doc"><t t-set="x" t-value="doc.name"/>^XA^XZ</t></t>',
            'label_fields': {'name': None},
            'width': 2,
            'height': 1,
            'dpi': 203,
            'orientation': 'normal',
            'designer_label_id': 'test-pdf-rights',
        }))
        label.convert_to_pdf = True
        user = new_test_user(self.env, login='zld_portal_pdf', groups='base.group_portal')
        other_partner = self.env['res.partner'].create({'name': 'Test Other Partner'})
        # A value in the cache is given without a check of the rights
        other_partner.invalidate_recordset()
        report = label.action_report_id.with_user(user)

        with patch(
            'odoo.addons.zpl_label_designer.models.ir_actions_report.generate_pdf_from_zpl',
            return_value=(b'%PDF', 1, {}),
        ) as generate_pdf, patch.object(type(self.env['ir.actions.report']), '_increment_labelary_request_counter'):
            self.assertEqual(report._generate_pdf_from_zpl_label(res_ids=[user.partner_id.id]), b'%PDF')
            generate_pdf.assert_called_once()
            generate_pdf.reset_mock()

            # QWeb wraps the access error into its own one, which differs between Odoo versions
            with mute_logger('odoo.addons.base.models.ir_qweb', 'odoo.addons.base.models.qweb'):
                with self.assertRaises(Exception):
                    report._generate_pdf_from_zpl_label(res_ids=[other_partner.id])

            generate_pdf.assert_not_called()

    def test_generated_template_is_saved_and_rendered(self):
        """
        Test that a template from the portal passes the checks and renders in the read-only call
        """
        label_id = self.Label._create_label({
            'name': 'Test Portal Label',
            'model': 'product.product',
            'qweb_xml': PORTAL_TEMPLATE,
            'label_fields': {'name': None},
            'width': 2,
            'height': 1,
            'dpi': 203,
            'orientation': 'normal',
            'designer_label_id': 'test-portal-label',
        })

        self.assertIn('^XA', self.Label.browse(label_id).preview)

    def test_report_name_expression_is_checked(self):
        """
        Test that a report name expression can't do what a formula can't: it runs for whoever opens the label
        """
        self.label.print_report_name = "'Label ' + (object.default_code or object.name)"

        with self.assertRaisesRegex(UserError, "can't use"):
            self.label.print_report_name = "object.sudo().name"

    def test_label_name_is_plain_text_in_report_name(self):
        """
        Test that the report name made from the label name is a plain string, whatever the name contains
        """
        for name in ["Men's label", 'Label "A"', "Label ' + 'A", 'Label \\ A']:
            with self.subTest(name=name):
                label = self.Label.browse(self.Label._create_label({
                    'name': name,
                    'model': 'product.product',
                    'qweb_xml': PORTAL_TEMPLATE,
                    'label_fields': {'name': None},
                    'width': 2,
                    'height': 1,
                    'dpi': 203,
                    'orientation': 'normal',
                    'designer_label_id': 'test-report-name',
                }))
                self.assertEqual(ast.literal_eval(label.action_report_id.print_report_name), name)

                label.name = name + ' new'
                label.publish()
                self.assertEqual(ast.literal_eval(label.action_report_id.print_report_name), name + ' new')

    def test_preview_can_not_change_data(self):
        """
        Test that a formula with a method nobody forbade can't write, and the transaction stays writable
        """
        self.company.enable_formulas = True
        category_name = 'Test Category From Formula'
        formula = "FORMULA:doc.categ_id.name_create('%s')" % category_name
        forbidden = 'odoo.addons.zpl_label_designer.models.zld_label.EXPRESSION_FORBIDDEN_ATTRIBUTES'

        with mute_logger('odoo.sql_db'), patch(forbidden, set()):
            with self.assertRaisesRegex(UserError, 'cannot be evaluated'):
                self.Label._get_preview_data('product.product', {formula: None})

        self.assertFalse(self.env['product.category'].search_count([('name', '=', category_name)]))

        data = self.Label._get_preview_data('product.product', {'FORMULA:doc.name': None})
        self.assertTrue(data['FORMULA:doc.name'])

        self.assertTrue(self.env['res.partner'].create({'name': 'Test Partner Still Writable'}))

    def test_validate_refuses_all_but_the_right_key(self):
        """
        Test that validate() lets in only the right key, compared by consteq(). A key that is not ASCII
        is a refusal too: consteq() raises an error on such text, which would be a server error
        """
        db = self.env.cr.dbname
        settings = self.env['res.config.settings']
        key = settings.get_zld_api_key()
        check = controller_utils.validate(lambda db: 'passed')
        request = MagicMock(env=self.env)

        with patch.object(controller_utils, 'request', request), \
                patch.object(controller_utils, 'db_filter', return_value=[db]), \
                patch.object(controller_utils, 'consteq', wraps=controller_utils.consteq) as consteq:
            request.httprequest.headers = {'ZLD-API-KEY': key}
            self.assertEqual(check(db=db), 'passed')
            consteq.assert_called_once()

            for headers in [{}, {'ZLD-API-KEY': 'wrong'}, {'ZLD-API-KEY': 'cl\xe9'}]:
                request.httprequest.headers = headers
                with self.subTest(headers=headers), self.assertRaises(Unauthorized):
                    check(db=db)

            # Without a key in the database, no key in the request must not count as a match
            request.httprequest.headers = {}
            with patch.object(type(settings), 'get_zld_api_key', return_value=False), self.assertRaises(Unauthorized):
                check(db=db)


@tagged('post_install', '-at_install', 'zld_security')  # can be run by test-tag
class TestZldPdfDownload(TestZldHttpCommon):
    """
    Tests of the rights a label converted to PDF is rendered with
    """

    def _download_label(self, login):
        self.authenticate(login, login)

        report = self.label.action_report_id
        url = '/report/text/%s/%s' % (report.report_name, self.product_id.id)

        return self.url_open('/report/download', data={
            'data': json.dumps([url, 'qweb-text']),
            'context': json.dumps({}),
            'token': 'dummy-because-api-expects-one',
            'csrf_token': http.Request.csrf_token(self),
        })

    def test_pdf_is_rendered_with_the_rights_of_the_user(self):
        """
        Test that a user who can't read the record doesn't get it as PDF, and a user who can does
        """
        self.label.convert_to_pdf = True
        generate_pdf = self._create_patch_object(ir_actions_report, 'generate_pdf_from_zpl')
        generate_pdf.return_value = (b'%PDF-1.4 label', 1, {})
        self._create_patch_object(type(self.env['ir.actions.report']), '_increment_labelary_request_counter')
        new_test_user(self.env, login='zld_portal', groups='base.group_portal')

        with mute_logger('odoo.addons.zpl_label_designer.controllers.report', 'odoo.http'):
            response = self._download_label('zld_portal')

        generate_pdf.assert_not_called()
        self.assertNotEqual(response.headers.get('Content-Type'), 'application/pdf')

        response = self._download_label('user_zld')

        generate_pdf.assert_called_once()
        self.assertEqual(response.headers.get('Content-Type'), 'application/pdf')
