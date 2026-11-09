# Copyright 2026 VentorTech OU
# See LICENSE file for full copyright and licensing details.

import difflib

from contextlib import contextmanager
from unittest.mock import patch
from odoo.tests import common


STOCK_USER_GROUP = 'stock.group_stock_user'
BASE_INTERNAL_USER_GROUP = 'base.group_user'

# ZPL template of a label as the Designer publishes it
TEST_LABEL_QWEB = '<t><t t-foreach="docs" t-as="doc">^XA^FO50,50^FD<t t-out="doc.display_name"/>^FS^XZ</t></t>'

# Keep in sync with printnode_base/tests/common.py, down to SPEC_KEYS
# (only there: self_readable and self_writeable in SPEC_KEYS)
# Printed as one block in the test log, so it can be copied from CI and sent to the Ventor PRO team
CONTRACT_BROKEN_MESSAGE = """
===== Ventor PRO API contract broken =====
Module: {module} {version}
Item: {item}
Problem: {problem}
{details}The Ventor PRO mobile app calls this directly. Keep it backward compatible,
or send this report to the Ventor PRO team and agree the change before release.
=========================================="""

# Keys a field spec may use. A misspelled key would silently skip its check, so it is rejected
SPEC_KEYS = {'type', 'comodel', 'related', 'required', 'selection_keys'}


class ZldCommonMixin:
    """
    Setup and helpers shared by TestZldCommon and TestZldHttpCommon
    """

    @classmethod
    def setUpClass(cls):
        super(ZldCommonMixin, cls).setUpClass()

        cls.company = cls.env.ref('base.main_company')

        # Warehouse user without ZPL Label Designer rights, as the mobile app works
        cls.user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'ZPL Label Designer User',
            'company_id': cls.company.id,
            'login': 'user_zld',
            'password': 'user_zld',
            'email': 'user@zld.test',
            'group_ids': [(6, 0, [
                cls.env.ref(STOCK_USER_GROUP).id,
                cls.env.ref(BASE_INTERNAL_USER_GROUP).id,
            ])]
        })

        # Second language to check attribute names and values in other languages
        cls.env['res.lang']._activate_lang('es_ES')

        # Attributes
        cls.attribute_diameter = cls._create_attribute('Test Diameter', ['22 mm'])
        cls.attribute_diameter.update_field_translations('name', {'es_ES': 'Test Diámetro'})
        cls.attribute_diameter.value_ids.update_field_translations('name', {'es_ES': '22 mm (ES)'})

        cls.attribute_size = cls._create_attribute('Test Size', ['S', 'M'])
        cls.attribute_length = cls._create_attribute(
            'Test Length', ['2800 m'], create_variant='no_variant')
        cls.attribute_material = cls._create_attribute(
            'Test Material', ['Wood', 'Metal'], create_variant='no_variant')

        # Products
        cls.product_tmpl = cls._create_product_template(
            'Test Product With Attributes',
            cls.attribute_diameter
            | cls.attribute_size
            | cls.attribute_length
            | cls.attribute_material,
        )
        cls.product_size_m = cls.product_tmpl.product_variant_ids.filtered(
            lambda product: 'M' in product.product_template_attribute_value_ids.mapped('name')
        )

        cls.product_without_attributes = cls.env['product.product'].create({
            'name': 'Test Product Without Attributes',
        })

        cls.product_id = cls.env['product.product'].create({
            'name': 'Test Product',
        })

        # Labels
        cls.label = cls._create_published_label('Test Label', 'product.product')

    @classmethod
    def _create_published_label(cls, name, model):
        """
        Create a published label with its view and report, as the Designer leaves them.

        Built from records only, without the module's private methods: a refactoring that keeps
        the data the same must not break the contract tests.
        """
        view = cls.env['ir.ui.view'].create({
            'type': 'qweb',
            'name': 'zpl_label_designer.test_label',
            'key': 'zpl_label_designer.test_label',
            'arch': TEST_LABEL_QWEB,
        })

        report = cls.env['ir.actions.report'].create({
            'name': name,
            'model': model,
            'report_type': 'qweb-text',
            'report_name': view.key,
            'report_file': view.key,
        })

        # The label wizard finds the report by its XML ID
        cls.env['ir.model.data'].create({
            'module': '__test__',
            'name': 'zld_test_label_action',
            'model': 'ir.actions.report',
            'res_id': report.id,
        })

        label = cls.env['zld.label'].create({
            'name': name,
            'model_id': cls.env['ir.model']._get_id(model),
            'dpi': 203,
            'view_id': view.id,
            'action_report_id': report.id,
            'is_published': True,
        })

        return label

    @classmethod
    def _create_attribute(cls, name, values, create_variant='always'):
        """
        Create a product attribute with the given values
        """
        return cls.env['product.attribute'].create({
            'name': name,
            'create_variant': create_variant,
            'value_ids': [(0, 0, {'name': value}) for value in values],
        })

    def _get_attribute_query_count(self, records, attr_name):
        """
        Count queries of getting the attribute of every record, as it is done on printing labels
        """
        self.env.flush_all()
        self.env.invalidate_all()

        # Printed records are browsed by their ids, so their fields are prefetched together
        records = records.browse(records.ids)
        query_count = self.cr.sql_log_count

        for record in records:
            record._get_attribute(attr_name)

        return self.cr.sql_log_count - query_count

    @classmethod
    def _create_product_template(cls, name, attributes):
        """
        Create a product template with all values of the given attributes
        """
        return cls.env['product.template'].create({
            'name': name,
            'attribute_line_ids': [
                (0, 0, {
                    'attribute_id': attribute.id,
                    'value_ids': [(6, 0, attribute.value_ids.ids)],
                })
                for attribute in attributes
            ],
        })

    # Keep in sync with printnode_base/tests/common.py
    def _create_patch_object(self, target, attribute):
        """
        Improved object patcher method from
        'https://docs.python.org/3/library/unittest.mock-examples.html#nesting-patches'

        This method makes it easier to work with unittest.mock.patch()<.object()> functions.
        It avoids extra nested indentation as when using patch() with the "with" context manager.
        """

        patcher = patch.object(target, attribute)
        thing = patcher.start()
        self.addCleanup(patcher.stop)
        return thing

    # Keep in sync with printnode_base/tests/common.py, from here to the end of the class
    # (only there: the self_readable/self_writeable checks in _assert_field_contract,
    # and _assert_methods_contract with _assert_method_contract)
    def _contract_message(self, item, problem, details=()):
        """
        Failure message of the Ventor PRO API contract tests.

        A block headed "Ventor PRO API contract broken", so a red pipeline says at once that the
        change may break the mobile app. It names the module and its version, what broke and,
        in `details`, what the item looks like now: the report is ready to send to the team.
        """
        module = self.env['ir.module.module']._get(self.test_module)
        return CONTRACT_BROKEN_MESSAGE.format(
            module=self.test_module,
            version=module.installed_version,
            item=item,
            problem=problem,
            details=''.join(f'{line}\n' for line in details),
        )

    def _similar_names(self, name, candidates):
        """
        Names close to `name`, to hint at what a renamed item is called now.

        Only a hint: a similar name may be another, older item.
        """
        similar = difflib.get_close_matches(name, list(candidates), n=5, cutoff=0.6)
        return ', '.join(similar) or 'none'

    @contextmanager
    def _assert_contract(self, item):
        """
        Turn an error raised by a call the app makes into a contract failure.

        Without it such an error shows up as a bare traceback that does not mention the app.
        The original error is kept in the message.
        """
        try:
            # A database error aborts the transaction, and the report could not read the module version
            with self.env.cr.savepoint():
                yield
        except AssertionError:
            raise
        except Exception as exc:
            self.fail(self._contract_message(item, f'{type(exc).__name__}: {exc}'))

    def _assert_contract_equal(self, actual, expected, item, problem):
        """
        assertEqual for values the app reads, with the expected and the actual value in the report
        """
        if actual != expected:
            self.fail(self._contract_message(item, problem, [
                f'Expected: {expected!r}',
                f'Now: {actual!r}',
            ]))

    def _assert_fields_contract(self, contract):
        """
        Check every field of a {model: {field: spec}} contract.

        Supported spec keys are in SPEC_KEYS, an unknown key raises ValueError.
        Each field is checked in its own subTest, so one run reports every broken field.
        """
        for model_name, fields_spec in contract.items():
            for field_name, spec in fields_spec.items():
                with self.subTest(field=f'{model_name}.{field_name}'):
                    self._assert_field_contract(model_name, field_name, spec)

    def _assert_field_contract(self, model_name, field_name, spec):
        item = f'{model_name}.{field_name}'

        unknown = set(spec) - SPEC_KEYS
        if unknown:
            raise ValueError(f'{item}: unknown contract spec keys {sorted(unknown)}')

        if model_name not in self.env:
            self.fail(self._contract_message(item, 'the model does not exist', [
                f'Similar models now: {self._similar_names(model_name, self.env.registry)}',
            ]))

        model = self.env[model_name]
        field = model._fields.get(field_name)
        if field is None:
            self.fail(self._contract_message(item, 'the field does not exist', [
                f'Similar fields now on {model_name}: {self._similar_names(field_name, model._fields)}',
            ]))

        changes = []
        if field.type != spec['type']:
            changes.append(f"Type: expected {spec['type']!r}, now {field.type!r}")
        if 'comodel' in spec and field.comodel_name != spec['comodel']:
            changes.append(f"Comodel: expected {spec['comodel']!r}, now {field.comodel_name!r}")
        if 'related' in spec and field.related != spec['related']:
            changes.append(f"Related: expected {spec['related']!r}, now {field.related!r}")
        if spec.get('required') and not field.required:
            changes.append('Required: expected True, now False')
        if 'selection_keys' in spec and field.type == 'selection':
            values = field.get_values(self.env)
            missing = [key for key in spec['selection_keys'] if key not in values]
            if missing:
                changes.append(f'Selection values missing: {", ".join(missing)}')
                changes.append(f'Selection values now: {", ".join(values)}')

        if changes:
            self.fail(self._contract_message(item, 'the field changed', changes))


class TestZldCommon(ZldCommonMixin, common.TransactionCase):
    """
    Setup to be used post-install with zpl_label_designer test configuration
    """


class TestZldHttpCommon(ZldCommonMixin, common.HttpCase):
    """
    Same setup as TestZldCommon, for tests that call routes over HTTP
    """
