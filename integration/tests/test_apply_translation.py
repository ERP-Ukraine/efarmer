# See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from .config.integration_init import OdooIntegrationInit, load_xml


NL_CODE = 'nl'
NL_CODE_FULL = 'nl_NL'
EN_CODE = 'en'
EN_CODE_FULL = 'en_US'
DE_CODE = 'de'
DE_CODE_FULL = 'de_DE'
IT_CODE = 'it'
IT_CODE_FULL = 'it_IT'
PL_CODE = 'pl'
PL_CODE_FULL = 'pl_PL'


@tagged('post_install', '-at_install', 'test_integration_core')
class TestTranslations(OdooIntegrationInit):

    @classmethod
    def setUpClass(cls):
        super(TestTranslations, cls).setUpClass()

        # Load base integration XML data first (needed for refs)
        load_xml(
            cls.env,
            module='integration',
            path_file='tests/data',
            filename='init_sale_integration.xml',
        )

        cls.lang_en = cls.env.ref('base.lang_en')
        cls.lang_nl = cls.env.ref('base.lang_nl')
        cls.lang_de = cls.env.ref('base.lang_de')
        cls.lang_it = cls.env.ref('base.lang_it')
        cls.lang_pl = cls.env.ref('base.lang_pl')

        lang_ids = [
            cls.lang_en.id,
            cls.lang_nl.id,
            cls.lang_de.id,
            cls.lang_it.id,
            cls.lang_pl.id,
        ]
        wizard_vals = dict(lang_ids=[(6, 0, lang_ids)])
        wizard = cls.env['base.language.install'].create(wizard_vals)
        wizard.lang_install()

        assert cls.lang_en.active is True
        assert cls.lang_en.code == EN_CODE_FULL
        assert cls.lang_en.iso_code == EN_CODE

        assert cls.lang_nl.active is True
        assert cls.lang_nl.code == NL_CODE_FULL
        assert cls.lang_nl.iso_code == NL_CODE

        assert cls.lang_de.active is True
        assert cls.lang_de.code == DE_CODE_FULL
        assert cls.lang_de.iso_code == DE_CODE

        assert cls.lang_it.active is True
        assert cls.lang_it.code == IT_CODE_FULL
        assert cls.lang_it.iso_code == IT_CODE

        assert cls.lang_pl.active is True
        assert cls.lang_pl.code == PL_CODE_FULL
        assert cls.lang_pl.iso_code == PL_CODE

        cls.translation_vals = {
            'name': 'Test Translation Product updated',
            'website_short_description': {
                'language': {
                    cls.lang_en.id: 'Description-X EN',
                    cls.lang_nl.id: 'Description-X NL'
                }
            }
        }

        # Access integration via env.ref since it's set up in parent's setUp (instance method)
        integration_no_api_1 = cls.env.ref('integration.integration_no_api_1')
        integration_no_api_1.integration_lang_id = cls.lang_en.id

    def test_context_language_no_matter(self):
        tmp_user = self.env['res.users'].create({
            'name': 'TempUser',
            'login': 'temp_user',
            'email': 'temp_user@mail.com',
            'password': 'password',
            'lang': NL_CODE_FULL,
            'company_id': self.company_id_1.id,
            'company_ids': self.company_id_1.ids,
            'groups_id': [(6, 0, [
                self.env.ref('sales_team.group_sale_manager').id,
                self.env.ref('stock.group_stock_manager').id,
                self.env.ref('account.group_account_manager').id,
            ])],
        })

        # Context has default EN language
        integration = self.integration_no_api_1

        # The tmp_user has NL language
        self.assertEqual(tmp_user.name, 'TempUser')
        self.assertEqual(tmp_user.lang, NL_CODE_FULL)

        # The integration_user has DE language
        self.integration_user.lang = DE_CODE_FULL
        self.assertEqual(self.integration_user.lang, DE_CODE_FULL)

        def _get_default_lang_patch(*args, **kw):
            return PL_CODE_FULL

        # The e-commerce shop has PL language
        self.patch(type(integration), 'get_shop_lang_code', _get_default_lang_patch)

        # Tests for the `get_integration_lang_code` method

        # 1. Change lang in context --> no matter
        code = integration.get_integration_lang_code()
        self.assertEqual(code, EN_CODE_FULL)

        code = integration.with_context(lang=IT_CODE_FULL).get_integration_lang_code()
        self.assertEqual(code, EN_CODE_FULL)

        # 2. Change lang for environment user --> no matter
        code = integration.with_context({}) \
            .with_user(self.integration_user.id).get_integration_lang_code()
        self.assertEqual(code, EN_CODE_FULL)

        code = integration.with_context({}).with_user(tmp_user.id).get_integration_lang_code()
        self.assertEqual(code, EN_CODE_FULL)

        # 3. Get code from e-commerce shop --> no matter
        self.integration_user.lang = False
        self.assertEqual(self.integration_user.lang, False)

        code = integration.with_context({}) \
            .with_user(self.integration_user.id).get_integration_lang_code()
        self.assertEqual(code, EN_CODE_FULL)

        tmp_user.lang = False
        self.assertEqual(tmp_user.lang, False)

        code = integration.with_context({}).with_user(tmp_user.id).get_integration_lang_code()
        self.assertEqual(code, EN_CODE_FULL)

    def test_apply_translation_external_lang_not_eq_erp_language(self):
        integration = self.integration_no_api_1

        # 1. Prepare product
        vals = dict(
            name='Test Translation Product',
            default_code='test-translation-product',
            integration_ids=[(6, 0, integration.ids)],
            website_short_description='Default Description EN',
        )
        template = integration.env['product.template'] \
            .with_user(self.integration_administrator).create(vals)

        self.assertEqual(template.default_code, 'test-translation-product')
        self.assertEqual(template.integration_ids, integration)

        # 2. Patch objects

        def _from_external_patch(*args, **kw):
            return self.lang_nl

        def _get_adapter_lang_code_patch(*args, **kw):
            return NL_CODE

        def _get_default_lang_patch(*args, **kw):
            return NL_CODE_FULL

        res_lang = template.env['res.lang']
        self.patch(type(res_lang), 'from_external', _from_external_patch)

        self.patch(type(integration), 'get_adapter_lang_code', _get_adapter_lang_code_patch)
        self.patch(type(integration), 'get_shop_lang_code', _get_default_lang_patch)

        self.assertTrue(
            integration.get_adapter_lang_code() == NL_CODE
        )
        self.assertTrue(
            integration.get_shop_lang_code() == NL_CODE_FULL
        )
        self.assertTrue(
            res_lang.from_external(integration, NL_CODE) == self.lang_nl
        )

        # 3. Tests
        self.assertEqual(
            template.with_context(lang=EN_CODE_FULL).website_short_description,
            'Default Description EN',
        )
        self.assertEqual(
            template.with_context(lang=EN_CODE_FULL).name,
            'Test Translation Product',
        )
        self.assertEqual(
            template.with_context(lang=NL_CODE_FULL).website_short_description,
            'Default Description EN',
        )
        self.assertEqual(
            template.with_context(lang=NL_CODE_FULL).name,
            'Test Translation Product',
        )

        External = template.env['integration.external.mixin']

        template_updated = External.create_or_update_with_translations(
            integration.id,
            template.with_context(skip_product_export=True),
            self.translation_vals,
        )

        self.assertEqual(
            str(template_updated.with_context(lang=NL_CODE_FULL).website_short_description),
            'Description-X NL',
        )
        self.assertEqual(
            template.with_context(lang=NL_CODE_FULL).name,
            'Test Translation Product updated',
        )
        self.assertEqual(
            str(template_updated.with_context(lang=EN_CODE_FULL).website_short_description),
            'Description-X EN',
        )
        self.assertEqual(
            template.with_context(lang=EN_CODE_FULL).name,
            'Test Translation Product updated',
        )

    def test_apply_translation_external_lang_eq_erp_language(self):
        integration = self.integration_no_api_1

        # 1. Prepare product
        vals = dict(
            name='Test Translation Product',
            default_code='test-translation-product',
            integration_ids=[(6, 0, integration.ids)],
            website_short_description='Default Description EN',
        )
        template = integration.env['product.template'] \
            .with_user(self.integration_administrator).create(vals)

        self.assertEqual(template.default_code, 'test-translation-product')
        self.assertEqual(template.integration_ids, integration)

        # 2. Patch objects

        def _from_external_patch(*args, **kw):
            return self.lang_en

        def _get_adapter_lang_code_patch(*args, **kw):
            return EN_CODE

        def _get_default_lang_patch(*args, **kw):
            return EN_CODE_FULL

        res_lang = template.env['res.lang']
        self.patch(type(res_lang), 'from_external', _from_external_patch)

        self.patch(type(integration), 'get_adapter_lang_code', _get_adapter_lang_code_patch)
        self.patch(type(integration), 'get_shop_lang_code', _get_default_lang_patch)

        self.assertTrue(
            integration.get_adapter_lang_code() == EN_CODE
        )
        self.assertTrue(
            integration.get_shop_lang_code() == EN_CODE_FULL
        )
        self.assertTrue(
            res_lang.from_external(integration, EN_CODE) == self.lang_en
        )

        # 3. Tests
        self.assertEqual(
            template.with_context(lang=EN_CODE_FULL).website_short_description,
            'Default Description EN',
        )
        self.assertEqual(
            template.with_context(lang=EN_CODE_FULL).name,
            'Test Translation Product',
        )
        self.assertEqual(
            template.with_context(lang=NL_CODE_FULL).website_short_description,
            'Default Description EN',
        )
        self.assertEqual(
            template.with_context(lang=NL_CODE_FULL).name,
            'Test Translation Product',
        )

        External = template.env['integration.external.mixin']

        template_updated = External.create_or_update_with_translations(
            integration.id,
            template.with_context(skip_product_export=True),
            self.translation_vals,
        )

        self.assertEqual(
            str(template_updated.with_context(lang=NL_CODE_FULL).website_short_description),
            'Description-X NL',
        )
        self.assertEqual(
            template.with_context(lang=NL_CODE_FULL).name,
            'Test Translation Product updated',
        )
        self.assertEqual(
            str(template_updated.with_context(lang=EN_CODE_FULL).website_short_description),
            'Description-X EN',
        )
        self.assertEqual(
            template.with_context(lang=EN_CODE_FULL).name,
            'Test Translation Product updated',
        )
