# See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged
from odoo.tools import mute_logger
from odoo.exceptions import UserError
from odoo.addons.integration.tools import Adapter

from .patch import ShopifyAPIClientPatchTest, ShopifyGraphQLPatchTest
from .init_integration_shopify import IntegrationShopifyBase


ORDER_ID = '100500'
ORDER_ID_FP = '100510'


@tagged('post_install', '-at_install')
class TestIntegrationShopify(IntegrationShopifyBase):

    def setUp(self):
        super(TestIntegrationShopify, self).setUp()

        # Activate all mapping fields
        self.env['product.ecommerce.field.mapping'].with_context(active_test=False).search([
            ('integration_id', '=', self.integration.id),
        ]).write({
            'active': True,
            'export_enabled': True,
            'import_enabled': True,
        })

    def test_get_product_accounts(self):
        # Product 1
        res = self.product1.product_tmpl_id.with_company(self.company).get_product_accounts()
        self.assertEqual(
            res['income'].id,
            self.env.ref('integration_shopify.integration_shopify_account_a_income').id,
        )
        self.assertEqual(
            res['expense'].id,
            self.env.ref('integration_shopify.integration_shopify_account_a_expense').id,
        )

        # Product 2
        res = self.product2.product_tmpl_id.with_company(self.company).get_product_accounts()
        self.assertEqual(
            res['income'].id,
            self.env.ref('integration_shopify.integration_shopify_account_a_income').id,
        )
        self.assertEqual(
            res['expense'].id,
            self.env.ref('integration_shopify.integration_shopify_account_a_expense').id,
        )

    def test_get_wh(self):
        self.assertEqual(self.integration._get_wh_from_external_location('73153839000'), self.wh)

    def test_integration_settings_patch(self):
        self.assertTrue(isinstance(self.adapter, Adapter))
        self.assertTrue(isinstance(self.adapter._Adapter__cache_core, ShopifyAPIClientPatchTest))
        self.assertTrue(isinstance(self.adapter.gql, ShopifyGraphQLPatchTest))

        self.assertEqual(self.adapter._integration_id, self.integration.id)
        self.assertEqual(self.adapter._integration_name, self.integration.name)

    @mute_logger('odoo.addons.integration.tools')
    def test_convert_product_fields_in_and_out(self):
        t, (v1, v2, v3, v4), errors = self.integration._import_external_product(
            ['10203545100500'],
            try_to_map=False,
        )

        # 1. Test external records
        self.assertEqual(t.name, 'E-guitar-test_az1u28399')
        self.assertEqual(t.code, '10203545100500')
        self.assertFalse(t.external_reference)
        self.assertFalse(t.external_barcode)

        self.assertEqual(v1.name, 'E-guitar-test_az1u28399')
        self.assertEqual(v2.name, 'E-guitar-test_az1u28399')
        self.assertEqual(v3.name, 'E-guitar-test_az1u28399')
        self.assertEqual(v4.name, 'E-guitar-test_az1u28399')

        self.assertEqual(v1.code, '10203545100500-51158197731620')
        self.assertEqual(v2.code, '10203545100500-51158197764388')
        self.assertEqual(v3.code, '10203545100500-51158197797156')
        self.assertEqual(v4.code, '10203545100500-51158197829924')

        self.assertEqual(v1.external_reference, 'e-guitar-gold-box-test_mdx3xoxx')
        self.assertEqual(v2.external_reference, 'e-guitar-gold-wood-test_mdx3xoxx')
        self.assertEqual(v3.external_reference, 'e-guitar-bronze-box-test_mdx3xoxx')
        self.assertEqual(v4.external_reference, 'e-guitar-bronze-wood-test_mdx3xoxx')

        self.assertEqual(v1.external_barcode, '321321321321')
        self.assertEqual(v2.external_barcode, '321321321322')
        self.assertEqual(v3.external_barcode, '321321321323')
        self.assertEqual(v4.external_barcode, '321321321324')

        self.assertFalse(errors)

        # 2. Test external-template fields IN
        data = t.calculate_import_fields_data()

        self.assertEqual(data['website_description'], "<p>It's just an e-guitar..</p>")
        self.assertEqual(data['sale_ok'], True)
        self.assertEqual(data['active'], True)
        self.assertEqual(data['is_storable'], True)
        self.assertEqual(data['website_seo_metatitle'], 'E-guitar-test_az1u28399-page-title')
        self.assertEqual(data['website_seo_description'], "It's just an e-guitar meta description")
        self.assertEqual(data['name'], 'E-guitar-test_az1u28399')

        self.assertEqual(data.get('feature_line_ids'), None)
        self.assertEqual(len(data['external_tag_group_ids']), 1)  # One group with tags

        self.assertEqual(len(data['integration_category_ids']), 1)
        self.assertEqual(data['integration_category_ids'][0][0], 6)
        self.assertEqual(data['integration_category_ids'][0][1], 0)
        self.assertTrue(data['integration_category_ids'][0][2].__class__, list)
        self.assertTrue(len(data['integration_category_ids'][0][2]), 2)
        self.assertTrue(data['integration_category_ids'][0][2][0].__class__, int)
        self.assertTrue(data['integration_category_ids'][0][2][1].__class__, int)

        # 3. Test external-variant fields IN
        data1 = v1.calculate_import_fields_data()

        self.assertEqual(data1['barcode'], '321321321321')
        self.assertEqual(round(data1['weight'], 1), 4.0)
        self.assertEqual(data1['default_code'], 'e-guitar-gold-box-test_mdx3xoxx')
        self.assertEqual(round(data1['variant_extra_price'], 2), 543.0)
        self.assertEqual(round(data1['standard_price'], 1), 490.0)

        data2 = v2.calculate_import_fields_data()

        self.assertEqual(data2['barcode'], '321321321322')
        self.assertEqual(round(data2['weight'], 1), 4.0)
        self.assertEqual(data2['default_code'], 'e-guitar-gold-wood-test_mdx3xoxx')
        self.assertEqual(round(data2['variant_extra_price'], 1), 542.0)
        self.assertEqual(round(data2['standard_price'], 1), 485.0)

        data3 = v3.calculate_import_fields_data()

        self.assertEqual(data3['barcode'], '321321321323')
        self.assertEqual(round(data3['weight'], 1), 4.0)
        self.assertEqual(data3['default_code'], 'e-guitar-bronze-box-test_mdx3xoxx')
        self.assertEqual(round(data3['variant_extra_price'], 1), 541.0)
        self.assertEqual(round(data3['standard_price'], 1), 480.0)

        data4 = v4.calculate_import_fields_data()

        self.assertEqual(data4['barcode'], '321321321324')
        self.assertEqual(round(data4['weight'], 1), 4.0)
        self.assertEqual(data4['default_code'], 'e-guitar-bronze-wood-test_mdx3xoxx')
        self.assertEqual(round(data4['variant_extra_price'], 1), 539.0)
        self.assertEqual(round(data4['standard_price'], 1), 475.0)

        # 4. Run import product
        template = t.import_one_product(import_images=False)
        self.assertEqual(template.name, 'E-guitar-test_az1u28399')
        self.assertEqual(template.product_variant_count, 4)
        self.assertEqual(
            set(template.external_tag_group_ids.mapped('tag_ids').mapped('name')),
            {'e-guitar', 'guitar'}
        )

        variant1, variant2, variant3, variant4 = template.product_variant_ids

        self.assertEqual(variant1.default_code, 'e-guitar-gold-box-test_mdx3xoxx')
        self.assertEqual(variant2.default_code, 'e-guitar-gold-wood-test_mdx3xoxx')
        self.assertEqual(variant3.default_code, 'e-guitar-bronze-box-test_mdx3xoxx')
        self.assertEqual(variant4.default_code, 'e-guitar-bronze-wood-test_mdx3xoxx')

        self.assertEqual(variant1.barcode, '321321321321')
        self.assertEqual(variant2.barcode, '321321321322')
        self.assertEqual(variant3.barcode, '321321321323')
        self.assertEqual(variant4.barcode, '321321321324')

        # 5. Test export-format
        data = template.to_export_format(self.integration)

        # 5.1 Template
        self.assertEqual(data['id'], template.id)
        self.assertEqual(data['odoo_external_id'], t.id)
        self.assertEqual(data['external_id'], t.code)
        self.assertEqual(data['gid'], f'gid://shopify/Product/{t.code}')
        self.assertEqual(data['type'], 'consu')
        self.assertEqual(data['kits'], [])
        self.assertEqual(data['variants_count'], 4)

        self.assertEqual(data['attribute_values'][0]['name'], 'Instrument color')
        self.assertEqual(data['attribute_values'][0]['values'][0]['name'], 'Gold')
        self.assertEqual(data['attribute_values'][0]['values'][1]['name'], 'Bronze')
        self.assertEqual(data['attribute_values'][1]['name'], 'Neck material')
        self.assertEqual(data['attribute_values'][1]['values'][0]['name'], 'Boxwood')
        self.assertEqual(data['attribute_values'][1]['values'][1]['name'], 'Wood')

        self.assertEqual(data['fields']['descriptionHtml'], '<p>It\'s just an e-guitar..</p>')
        self.assertEqual(data['fields']['status'], 'ACTIVE')
        self.assertEqual(
            data['fields']['collectionsToJoin'],
            ['gid://shopify/Collection/440312267044', 'gid://shopify/Collection/440313119012'],
        )
        self.assertEqual(data['fields']['tags'], ['e-guitar', 'guitar'])
        self.assertEqual(data['fields']['title'], 'E-guitar-test_az1u28399')

        self.assertEqual(data['fields']['metafields'][0]['key'], 'title_tag')
        self.assertEqual(data['fields']['metafields'][0]['value'], 'E-guitar-test_az1u28399-page-title')
        self.assertEqual(data['fields']['metafields'][0]['namespace'], 'global')
        self.assertEqual(data['fields']['metafields'][0]['type'], 'single_line_text_field')
        self.assertFalse(bool(data['fields']['metafields'][0].get('_translation_key')))

        self.assertEqual(data['fields']['metafields'][1]['key'], 'description_tag')
        self.assertEqual(data['fields']['metafields'][1]['value'], 'It\'s just an e-guitar meta description')
        self.assertEqual(data['fields']['metafields'][1]['namespace'], 'global')
        self.assertEqual(data['fields']['metafields'][1]['type'], 'multi_line_text_field')
        self.assertFalse(bool(data['fields']['metafields'][1].get('_translation_key')))

        # 5.2 Variant 1
        data1 = data['products'][0]

        self.assertEqual(data1['id'], variant1.id)
        self.assertEqual(data1['odoo_external_id'], v1.id)
        self.assertEqual(data1['external_id'], v1.code)
        self.assertEqual(data1['reference'], v1.external_reference)
        self.assertEqual(data1['reference'], variant1.default_code)
        self.assertEqual(data1['reference_api_field'], 'sku')
        self.assertEqual(data1['gid'], f'gid://shopify/ProductVariant/{v1.code.rsplit("-", 1)[-1]}')

        self.assertEqual(data1['attribute_values'][0]['optionName'], 'Instrument color')
        self.assertEqual(data1['attribute_values'][0]['name'], 'Gold')
        self.assertEqual(data1['attribute_values'][1]['optionName'], 'Neck material')
        self.assertEqual(data1['attribute_values'][1]['name'], 'Boxwood')

        self.assertEqual(data1['fields']['barcode'], v1.external_barcode)
        self.assertEqual(data1['fields']['barcode'], variant1.barcode)
        self.assertEqual(data1['fields']['inventoryItem']['sku'], variant1.default_code)
        self.assertEqual(round(data1['fields']['price'], 1), 543.0)
        self.assertEqual(data1['fields']['compareAtPrice'], 0)
        self.assertEqual(data1['fields']['taxable'], True)
        self.assertEqual(round(data1['fields']['inventoryItem']['measurement']['weight']['value'], 1), 4.0)
        self.assertEqual(data1['fields']['inventoryItem']['measurement']['weight']['unit'], 'KILOGRAMS')
        self.assertEqual(round(data1['fields']['inventoryItem']['cost'], 1), 490.0)

        # 5.3 Variant 2
        data2 = data['products'][1]

        self.assertEqual(data2['id'], variant2.id)
        self.assertEqual(data2['odoo_external_id'], v2.id)
        self.assertEqual(data2['external_id'], v2.code)
        self.assertEqual(data2['reference'], v2.external_reference)
        self.assertEqual(data2['reference'], variant2.default_code)
        self.assertEqual(data2['reference_api_field'], 'sku')
        self.assertEqual(data2['gid'], f'gid://shopify/ProductVariant/{v2.code.rsplit("-", 1)[-1]}')

        self.assertEqual(data2['attribute_values'][0]['optionName'], 'Instrument color')
        self.assertEqual(data2['attribute_values'][0]['name'], 'Gold')
        self.assertEqual(data2['attribute_values'][1]['optionName'], 'Neck material')
        self.assertEqual(data2['attribute_values'][1]['name'], 'Wood')

        self.assertEqual(data2['fields']['barcode'], v2.external_barcode)
        self.assertEqual(data2['fields']['barcode'], variant2.barcode)
        self.assertEqual(data2['fields']['inventoryItem']['sku'], variant2.default_code)
        self.assertEqual(round(data2['fields']['price'], 1), 542.0)
        self.assertEqual(data2['fields']['compareAtPrice'], 0)
        self.assertEqual(data2['fields']['taxable'], True)
        self.assertEqual(round(data2['fields']['inventoryItem']['measurement']['weight']['value'], 1), 4.0)
        self.assertEqual(data2['fields']['inventoryItem']['measurement']['weight']['unit'], 'KILOGRAMS')
        self.assertEqual(round(data2['fields']['inventoryItem']['cost'], 1), 485.0)

        # 5.4 Variant 3
        data3 = data['products'][2]

        self.assertEqual(data3['id'], variant3.id)
        self.assertEqual(data3['odoo_external_id'], v3.id)
        self.assertEqual(data3['external_id'], v3.code)
        self.assertEqual(data3['reference'], v3.external_reference)
        self.assertEqual(data3['reference'], variant3.default_code)
        self.assertEqual(data3['reference_api_field'], 'sku')
        self.assertEqual(data3['gid'], f'gid://shopify/ProductVariant/{v3.code.rsplit("-", 1)[-1]}')

        self.assertEqual(data3['attribute_values'][0]['optionName'], 'Instrument color')
        self.assertEqual(data3['attribute_values'][0]['name'], 'Bronze')
        self.assertEqual(data3['attribute_values'][1]['optionName'], 'Neck material')
        self.assertEqual(data3['attribute_values'][1]['name'], 'Boxwood')

        self.assertEqual(data3['fields']['barcode'], v3.external_barcode)
        self.assertEqual(data3['fields']['barcode'], variant3.barcode)
        self.assertEqual(data3['fields']['inventoryItem']['sku'], variant3.default_code)
        self.assertEqual(round(data3['fields']['price'], 1), 541.0)
        self.assertEqual(data3['fields']['compareAtPrice'], 0)
        self.assertEqual(data3['fields']['taxable'], True)
        self.assertEqual(round(data3['fields']['inventoryItem']['measurement']['weight']['value'], 1), 4.0)
        self.assertEqual(data3['fields']['inventoryItem']['measurement']['weight']['unit'], 'KILOGRAMS')
        self.assertEqual(round(data3['fields']['inventoryItem']['cost'], 1), 480.0)

        # 5.5 Variant 4
        data4 = data['products'][3]

        self.assertEqual(data4['id'], variant4.id)
        self.assertEqual(data4['odoo_external_id'], v4.id)
        self.assertEqual(data4['external_id'], v4.code)
        self.assertEqual(data4['reference'], v4.external_reference)
        self.assertEqual(data4['reference'], variant4.default_code)
        self.assertEqual(data4['reference_api_field'], 'sku')
        self.assertEqual(data4['gid'], f'gid://shopify/ProductVariant/{v4.code.rsplit("-", 1)[-1]}')

        self.assertEqual(data4['attribute_values'][0]['optionName'], 'Instrument color')
        self.assertEqual(data4['attribute_values'][0]['name'], 'Bronze')
        self.assertEqual(data4['attribute_values'][1]['optionName'], 'Neck material')
        self.assertEqual(data4['attribute_values'][1]['name'], 'Wood')

        self.assertEqual(data4['fields']['barcode'], v4.external_barcode)
        self.assertEqual(data4['fields']['barcode'], variant4.barcode)
        self.assertEqual(data4['fields']['inventoryItem']['sku'], variant4.default_code)
        self.assertEqual(round(data4['fields']['price'], 1), 539.0)
        self.assertEqual(data4['fields']['compareAtPrice'], 0)
        self.assertEqual(data4['fields']['taxable'], True)
        self.assertEqual(round(data4['fields']['inventoryItem']['measurement']['weight']['value'], 1), 4.0)
        self.assertEqual(data4['fields']['inventoryItem']['measurement']['weight']['unit'], 'KILOGRAMS')
        self.assertEqual(round(data4['fields']['inventoryItem']['cost'], 1), 475.0)

    @mute_logger('odoo.addons.integration.tools')
    def test_fetch_order(self):
        adapter = self.integration.adapter
        order_dict = adapter.receive_order(ORDER_ID)
        data = order_dict['data']

        order = adapter.gql.Order.set(**data)

        self.assertEqual(order.id, int(ORDER_ID))
        self.assertEqual(order.name, '#1166')
        self.assertEqual(order.parse_currency_code(), 'PLN')

        customer = order.customer

        self.assertEqual(customer.id, 6670178025000)
        self.assertEqual(customer.email, 'przecietny-kowalski@mail.pl')
        self.assertEqual(customer.first_name, 'Przeciętny')
        self.assertEqual(customer.last_name, 'Kowalski')
        self.assertEqual(customer.default_address.first_name, 'Przeciętny')
        self.assertEqual(customer.default_address.last_name, 'Kowalski')

        self.assertFalse(order.billing_address)
        self.assertFalse(order.shipping_address)
        self.assertTrue(order.billing_matches_shipping)

        addresses = order.parse_customer_data()

        self.assertEqual(addresses['customer']['id'], '6670178025000')
        self.assertEqual(addresses['customer']['email'], 'przecietny-kowalski@mail.pl')
        self.assertEqual(addresses['customer']['phone'], '+48123234456')
        self.assertEqual(addresses['customer']['person_name'], 'Przeciętny Kowalski')
        self.assertEqual(addresses['customer']['customer_locale'], 'pl')

        # Use default Customer address due to not order.billing_address
        self.assertEqual(addresses['billing']['phone'], '+48123234346')
        self.assertEqual(addresses['billing']['person_name'], 'Przeciętny Kowalski')
        self.assertEqual(addresses['billing']['customer_locale'], 'pl')
        self.assertEqual(addresses['billing']['company_name'], 'Przeciętny COmpany')
        self.assertEqual(addresses['billing']['street'], 'Księdza Pawła Lexa 100')
        self.assertEqual(addresses['billing']['street2'], '')
        self.assertEqual(addresses['billing']['city'], 'Ruda Śląska')
        self.assertEqual(addresses['billing']['country_code'], 'PL')
        self.assertEqual(addresses['billing']['state_code'], '')
        self.assertEqual(addresses['billing']['zip'], '01-123')
        self.assertEqual(addresses['billing']['type'], 'invoice')

        # Use default Customer address due to not order.shipping_address and order.shipping_matches_shipping
        self.assertEqual(addresses['shipping']['phone'], '+48123234346')
        self.assertEqual(addresses['shipping']['person_name'], 'Przeciętny Kowalski')
        self.assertEqual(addresses['shipping']['customer_locale'], 'pl')
        self.assertEqual(addresses['shipping']['company_name'], 'Przeciętny COmpany')
        self.assertEqual(addresses['shipping']['street'], 'Księdza Pawła Lexa 100')
        self.assertEqual(addresses['shipping']['street2'], '')
        self.assertEqual(addresses['shipping']['city'], 'Ruda Śląska')
        self.assertEqual(addresses['shipping']['country_code'], 'PL')
        self.assertEqual(addresses['shipping']['state_code'], '')
        self.assertEqual(addresses['shipping']['zip'], '01-123')
        self.assertFalse(addresses['shipping'].get('type', False))

        self.assertFalse(bool(order.delivery_method))  # Due to the shipping_line is null

        self.assertEqual(order.tags, ['ttag1', 'ttag2'])
        self.assertEqual(order.note, 'Just note from customer')
        self.assertEqual(order.location_id, '73153839396')
        self.assertFalse(order.publication)

        self.assertEqual(len(order.fulfillments), 2)
        self.assertEqual(len(order.fulfillment_orders), 1)
        self.assertEqual(len(order.line_items), 2)

    @mute_logger('odoo.addons.integration.tools')
    def test_create_order_from_input(self):
        # 1. Create input file
        self.integration.test_method_parameter = ORDER_ID
        input_file = self.integration.integrationApiReceiveOrder()

        self.assertEqual(input_file.si_id.id, self.integration.id)
        self.assertEqual(input_file.name, ORDER_ID)
        self.assertFalse(input_file.order_id)
        self.assertTrue(input_file.update_required)

        # 2. Create order from input file
        input_file.update_required = False
        input_file = self._set_permissions(input_file)

        parsed_data = input_file.parse()
        self.assertEqual(parsed_data['id'], ORDER_ID)
        self.assertEqual(parsed_data['external_location_id'], '73153839396')

        order = input_file.process_no_job()

        # 2.1 Check order
        self.assertEqual(order.name, '#1166')
        self.assertEqual(len(order.order_line), 2)
        self.assertEqual(order.company_id, self.company)
        self.assertEqual(order.currency_id, self.env.ref('base.PLN'))

        self.assertEqual(order.partner_id.type, 'contact')
        self.assertEqual(order.partner_id.company_type, 'person')
        self.assertEqual(order.partner_id.name, 'Przeciętny Kowalski')
        self.assertEqual(order.partner_id.city, 'Ruda Śląska')
        self.assertEqual(order.partner_id.phone.replace(' ', ''), '+48123234346')
        self.assertEqual(order.partner_id.email, 'przecietny-kowalski@mail.pl')
        self.assertEqual(order.partner_id.country_id, self.env.ref('base.pl'))
        self.assertEqual(order.partner_id.zip, '01-123')
        self.assertEqual(order.partner_id.street, 'Księdza Pawła Lexa 100')
        self.assertFalse(order.partner_id.company_name)
        self.assertFalse(order.partner_id.is_company)
        self.assertEqual(order.partner_id.lang, self.env.ref('base.lang_pl').code)
        self.assertEqual(order.partner_id.category_id.name, self.integration.name)

        self.assertEqual(order.pricelist_id.company_id, self.company)
        self.assertEqual(order.pricelist_id.currency_id, self.env.ref('base.PLN'))

        self.assertEqual(round(order.amount_untaxed, 1), 1746.0)
        self.assertEqual(round(order.amount_tax, 2), 401.58)
        self.assertEqual(round(order.amount_total, 2), 2147.58)

        # First line
        line = order.order_line[0]
        self.assertEqual(line.warehouse_id, self.wh)
        self.assertEqual(line.product_id.default_code, 'gtp3-ref-1-shopify-test')
        self.assertEqual(round(line.product_qty, 2), 2.0)
        self.assertEqual(round(line.qty_to_deliver, 2), 2.0)

        self.assertEqual(round(line.price_unit, 1), 123.0)
        self.assertEqual(round(line.price_subtotal, 1), 246.0)
        self.assertEqual(round(line.price_tax, 2), 56.58)
        self.assertEqual(round(line.price_total, 2), 302.58)

        # Second line
        line = order.order_line[1]
        self.assertEqual(line.warehouse_id, self.wh)
        self.assertEqual(line.product_id.default_code, 'guit1-sku-bl-shopify-test')
        self.assertEqual(round(line.product_qty, 1), 3.0)
        self.assertEqual(round(line.qty_to_deliver, 1), 3.0)

        self.assertEqual(round(line.price_unit, 1), 500.0)
        self.assertEqual(round(line.price_subtotal, 1), 1500.0)
        self.assertEqual(round(line.price_tax, 1), 345.0)
        self.assertEqual(round(line.price_total, 0), 1845)

        # 2.2 Integration fields
        self.assertEqual(order.integration_id, self.integration)

        self.assertEqual(order.sub_status_id.name, 'Paid')
        self.assertEqual(order.shopify_fulfilment_status.name, 'Fulfilled')

        self.assertEqual(order.payment_method_id.integration_id, self.integration)
        self.assertEqual(order.payment_method_id.name, 'manual_in_shopify_test')
        self.assertEqual(order.external_sales_order_ref, '#1166')

        self.assertEqual(len(order.external_tag_ids), 2)
        self.assertEqual(order.external_tag_ids.integration_id, self.integration)
        self.assertEqual(set(order.external_tag_ids.mapped('name')), {'ttag1', 'ttag2'})

        self.assertEqual(len(order.external_fulfillment_ids), 2)
        self.assertEqual(order.external_fulfillment_ids.integration_id, self.integration)
        self.assertEqual(set(order.external_fulfillment_ids.mapped('name')), {'#1166-F1', '#1166-F2'})
        self.assertEqual(set(order.external_fulfillment_ids.mapped('external_status')), {'success'})
        self.assertEqual(set(order.external_fulfillment_ids.mapped('internal_status')), {'draft'})

        self.assertEqual(len(order.external_payment_ids), 1)
        self.assertEqual(order.external_payment_ids.integration_id, self.integration)
        self.assertEqual(order.external_payment_ids.external_str_id, '10679267000000')
        self.assertEqual(order.external_payment_ids.amount, '147.58')
        self.assertEqual(order.external_payment_ids.currency, 'PLN')

        self.assertEqual(len(order.order_risk_ids), 0)

        # 2.3 Check pipeline
        pipeline = order.integration_pipeline
        pipeline.ensure_one()
        self.assertTrue(all(pipeline.pipeline_task_ids.mapped(lambda x: x.state == 'skip')))
        self.assertEqual(set(pipeline.sub_state_external_ids.mapped('code')), {'paid', 'fulfilled'})
        self.assertFalse(pipeline.skip_dispatch)
        self.assertFalse(pipeline.invoice_journal_id)
        self.assertFalse(pipeline.payment_journal_id)
        self.assertFalse(pipeline.current_info)
        self.assertEqual(pipeline.input_file_id, input_file)

        # 3. Run pipeline

        # Activate tasks
        pipeline.pipeline_task_ids.write({'state': 'todo'})
        self.integration.apply_external_fulfillments = True  # Create two pickings automatically (Shopify feature)
        self.integration.apply_external_payments = True  # Create payments automatically (Shopify feature)

        self.env['stock.quant'].create({
            'product_id': self.product1.id,
            'location_id': self.wh.lot_stock_id.id,
            'quantity': 100,
        })
        self.env['stock.quant'].create({
            'product_id': self.product2.id,
            'location_id': self.wh.lot_stock_id.id,
            'quantity': 100,
        })

        # 3.1 validate_order
        task1 = pipeline.pipeline_task_ids.filtered(lambda x: x.current_step_method == 'validate_order')

        self.assertEqual(order.state, 'draft')
        self.assertEqual(len(order.picking_ids), 0)

        task1.run()

        self.assertEqual(task1.state, 'done')
        self.assertEqual(set(order.external_fulfillment_ids.mapped('internal_status')), {'done'})

        self.assertEqual(order.state, 'sale')
        self.assertEqual(order.delivery_status, 'full')
        self.assertEqual(order.invoice_status, 'to invoice')
        self.assertEqual(len(order.picking_ids), 2)
        self.assertEqual(order.picking_ids[0].state, 'done')
        self.assertEqual(order.picking_ids[1].state, 'done')

        # 3.2 validate_picking
        task2 = pipeline.pipeline_task_ids.filtered(lambda x: x.current_step_method == 'validate_picking')
        self.assertEqual(task2.state, 'todo')

        task2.run()

        self.assertEqual(task2.state, 'done')
        self.assertEqual(len(order.picking_ids), 2)

        # 3.3 create_invoice
        task3 = pipeline.pipeline_task_ids.filtered(lambda x: x.current_step_method == 'create_invoice')
        self.assertEqual(task3.state, 'todo')

        with self.assertRaises(UserError) as ex:
            task3.run()

        self.assertIn('No Invoice Journal defined', str(ex.exception))

        pipeline.sub_state_external_ids\
            .filtered(lambda x: x.code == 'paid') \
            .invoice_journal_id = self.invoice_journal.id

        self.assertEqual(pipeline.invoice_journal_id, self.invoice_journal)

        # Define partner's accounts
        partner = order.partner_id.with_company(self.company)
        partner.property_account_receivable_id = self.env.ref('integration_shopify.integration_shopify_account_a_recv')
        partner.property_account_payable_id = self.env.ref('integration_shopify.integration_shopify_account_a_pay')

        task3.run()

        self.assertEqual(task3.state, 'done')

        self.assertEqual(order.invoice_status, 'invoiced')

        invoice = order.actual_invoice_ids
        self.assertEqual(len(invoice), 1)
        self.assertEqual(invoice.state, 'draft')
        self.assertEqual(invoice.invoice_origin, order.name)
        self.assertEqual(invoice.move_type, 'out_invoice')
        self.assertEqual(invoice.country_code, 'PL')
        self.assertEqual(invoice.currency_id, self.env.ref('base.PLN'))
        self.assertEqual(invoice.payment_state, 'not_paid')
        self.assertEqual(invoice.integration_id, self.integration)
        self.assertEqual(round(invoice.amount_untaxed, 1), 1746.0)
        self.assertEqual(round(invoice.amount_tax, 2), 401.58)
        self.assertEqual(round(invoice.amount_total, 2), 2147.58)
        self.assertEqual(round(invoice.amount_residual, 2), 2147.58)

        # 3.4 validate_invoice
        task4 = pipeline.pipeline_task_ids.filtered(lambda x: x.current_step_method == 'validate_invoice')

        self.assertEqual(task4.state, 'todo')

        # first attempt
        with self.assertRaises(UserError) as ex:
            task4.run()  # Assert applying external payments

        self.assertTrue(
            f'No Payment Journal defined for Payment Method "{order.payment_method_id.name}"' in str(ex.exception)
        )

        journal = self.env.ref('integration_shopify.integration_shopify_account_cash_journal')
        pipeline.payment_method_external_id.payment_journal_id = journal.id

        def _get_outstanding_account_patch(self, payment_type):
            if payment_type == 'inbound':
                return self.env.ref('integration_shopify.integration_shopify_account_debit')
            return self.env['account.account']

        self.patch(type(self.env['account.payment']), '_get_outstanding_account', _get_outstanding_account_patch)

        # second attempt
        task4.run()

        self.assertEqual(task4.state, 'done')
        self.assertEqual(set(order.external_payment_ids.mapped('internal_status')), {'done'})

        self.assertEqual(invoice.state, 'posted')
        self.assertEqual(round(invoice.amount_residual, 1), 2000.0)

        self.assertEqual(invoice.payment_state, 'partial')

        payment = self.env['account.payment'].search([('invoice_ids', 'in', invoice.id)])
        payment.ensure_one()
        self.assertEqual(payment.state, 'paid')
        self.assertEqual(round(payment.amount, 2), 147.58)

        # 3.5 send invoice
        task5 = pipeline.pipeline_task_ids.filtered(lambda x: x.current_step_method == 'send_invoice')
        self.assertEqual(task5.state, 'todo')

        # Patch wizard action to avoid actually sending email
        def _mock_action_send_and_print(self):
            invoice.write({'is_move_sent': True})
            return {'type': 'ir.actions.act_window_close'}  # Simulate success

        self.patch(
            type(self.env['account.move.send.wizard']),
            'action_send_and_print',
            _mock_action_send_and_print,
        )

        self.assertFalse(invoice.is_move_sent)

        task5.run()

        self.assertEqual(task5.state, 'done')
        self.assertTrue(invoice.is_move_sent)

        # 3.6 register_payment
        task6 = pipeline.pipeline_task_ids.filtered(lambda x: x.current_step_method == 'register_payment')
        self.assertEqual(task6.state, 'todo')

        def _get_available_payment_method_lines_patch(self, payment_type):
            if not self:
                return self.env['account.payment.method.line']

            self.ensure_one()
            if payment_type == 'inbound':
                return self.env.ref('integration_shopify.integration_shopify_line_check_in')

            return journal.outbound_payment_method_line_ids

        self.patch(type(journal), '_get_available_payment_method_lines', _get_available_payment_method_lines_patch)

        task6.run()

        self.assertEqual(task6.state, 'done')

        self.assertEqual(round(invoice.amount_residual, 1), 0.0)
        self.assertEqual(invoice.payment_state, 'paid')

        payments = self.env['account.payment'].search([('invoice_ids', 'in', invoice.id)])
        self.assertEqual(len(payments), 2)
        self.assertEqual(payments[0].state, 'paid')
        self.assertEqual(payments[1].state, 'paid')
        self.assertEqual(round(sum(payments.mapped('amount')), 2), 2147.58)

    @mute_logger('odoo.addons.integration.tools')
    def test_order_fiscal_position(self):
        # 1. Create input file
        self.integration.test_method_parameter = ORDER_ID_FP
        input_file = self.integration.integrationApiReceiveOrder()

        self.assertEqual(input_file.si_id.id, self.integration.id)
        self.assertEqual(input_file.name, ORDER_ID_FP)
        self.assertFalse(input_file.order_id)
        self.assertTrue(input_file.update_required)

        # 2. Parse order from input file
        input_file.update_required = False
        input_file = self._set_permissions(input_file)

        parsed_data = input_file.parse()

        self.assertEqual(parsed_data['id'], ORDER_ID_FP)
        self.assertEqual(parsed_data['customer']['email'], 'j.hatf.shopify.test@myshopify.test.com')
        self.assertEqual(parsed_data['customer']['person_name'], 'James Hatf')
        self.assertEqual(parsed_data['customer']['phone'], '+48534612001')
        self.assertEqual(parsed_data['customer']['customer_locale'], 'pl')

        # Billing
        self.assertEqual(parsed_data['billing']['type'], 'invoice')
        self.assertEqual(parsed_data['billing']['phone'], '+48534612001')
        self.assertEqual(parsed_data['billing']['email'], 'j.hatf.shopify.test@myshopify.test.com')
        self.assertEqual(parsed_data['billing']['person_name'], 'James Hatf')
        self.assertEqual(parsed_data['billing']['company_name'], 'J. Hat Co')
        self.assertEqual(parsed_data['billing']['customer_locale'], 'pl')
        self.assertEqual(parsed_data['billing']['street'], 'Trojanowska 71')
        self.assertEqual(parsed_data['billing']['street2'], '')
        self.assertEqual(parsed_data['billing']['city'], 'Sochaczew')
        self.assertEqual(parsed_data['billing']['country_code'], 'PL')
        self.assertEqual(parsed_data['billing']['state_code'], '')
        self.assertEqual(parsed_data['billing']['zip'], '96-500')

        # Shipping
        self.assertFalse(parsed_data['shipping'].get('type'))
        self.assertEqual(parsed_data['shipping']['phone'], '+48534612001')
        self.assertEqual(parsed_data['shipping']['email'], 'j.hatf.shopify.test@myshopify.test.com')
        self.assertEqual(parsed_data['shipping']['person_name'], 'James Hatf')
        self.assertEqual(parsed_data['shipping']['company_name'], 'J. Hat Co')
        self.assertEqual(parsed_data['shipping']['customer_locale'], 'pl')
        self.assertEqual(parsed_data['shipping']['street'], 'Trojanowska 72')
        self.assertEqual(parsed_data['shipping']['street2'], '')
        self.assertEqual(parsed_data['shipping']['city'], 'Sochaczew')
        self.assertEqual(parsed_data['shipping']['country_code'], 'PL')
        self.assertEqual(parsed_data['shipping']['state_code'], '')
        self.assertEqual(parsed_data['shipping']['zip'], '96-500')

        # 2. Create customer from parsed data
        PartnerFactory = self.env['integration.res.partner.factory'].create_factory(
            self.integration.id,
            customer_data=parsed_data['customer'],
            billing_data=parsed_data['billing'],
            shipping_data=parsed_data['shipping'],
        )

        partner, addresses = PartnerFactory.get_partner_and_addresses()

        # 2.1 Partner
        self.assertEqual(partner.name, 'James Hatf')
        self.assertFalse(partner.company_name)
        self.assertFalse(partner.external_company_name)
        self.assertEqual(partner.email, 'j.hatf.shopify.test@myshopify.test.com')
        self.assertEqual(partner.phone.replace(' ', ''), '+48534612001')
        self.assertEqual(partner.lang, self.env.ref('base.lang_pl').code)
        self.assertEqual(partner.category_id.name, self.integration.name)

        self.assertEqual(partner.commercial_partner_id.type, 'contact')
        self.assertEqual(partner.commercial_partner_id.name, 'J. Hat Co')
        self.assertEqual(partner.commercial_partner_id.company_type, 'company')

        # 2.2 Partner parent
        self.assertTrue(partner.parent_id)
        self.assertTrue(partner.parent_id.name, 'J. Hat Co')
        self.assertTrue(partner.parent_id.type, 'contact')
        self.assertTrue(partner.parent_id.company_type, 'company')

        # 2.3 Billing
        billing = addresses['billing']

        # self.assertEqual(billing.type, 'invoice') # TODO: Fix it: on gitlab it is a 'contact'
        self.assertEqual(billing.company_type, 'person')
        # self.assertEqual(billing.external_company_name, 'J. Hat Co')  # TODO: Fix it: on gitlab it is False
        self.assertEqual(billing.name, 'James Hatf')
        self.assertEqual(billing.city, 'Sochaczew')
        self.assertEqual(billing.street, 'Trojanowska 71')
        self.assertFalse(billing.street2)
        self.assertEqual(billing.phone.replace(' ', ''), '+48534612001')
        self.assertEqual(billing.email, 'j.hatf.shopify.test@myshopify.test.com')
        self.assertEqual(billing.country_id, self.env.ref('base.pl'))
        self.assertEqual(billing.zip, '96-500')
        self.assertFalse(billing.company_name)
        self.assertFalse(billing.is_company)
        self.assertEqual(billing.lang, self.env.ref('base.lang_pl').code)
        self.assertEqual(billing.category_id.name, self.integration.name)
        self.assertEqual(billing.commercial_partner_id.id, partner.commercial_partner_id.id)

        # 2.4 Shipping
        shipping = addresses['shipping']

        self.assertEqual(shipping.type, 'delivery')
        self.assertEqual(shipping.company_type, 'person')
        self.assertEqual(shipping.external_company_name, 'J. Hat Co')
        self.assertEqual(shipping.name, 'James Hatf')
        self.assertEqual(shipping.city, 'Sochaczew')
        self.assertEqual(shipping.street, 'Trojanowska 72')
        self.assertFalse(shipping.street2)
        self.assertEqual(shipping.phone.replace(' ', ''), '+48534612001')
        self.assertEqual(shipping.email, 'j.hatf.shopify.test@myshopify.test.com')
        self.assertEqual(shipping.country_id, self.env.ref('base.pl'))
        self.assertEqual(shipping.zip, '96-500')
        self.assertFalse(shipping.company_name)
        self.assertFalse(shipping.is_company)
        self.assertEqual(shipping.lang, self.env.ref('base.lang_en').code)  # TODO: fix it
        self.assertEqual(shipping.category_id.name, self.integration.name)
        self.assertEqual(shipping.commercial_partner_id.id, partner.commercial_partner_id.id)

        tax_23 = self.env.ref('integration_shopify.integration_shopify_account_tax_23')
        tax_21 = self.env.ref('integration_shopify.integration_shopify_account_tax_21')

        # 3. Process input file without customer's fiscal position
        order = input_file.process_no_job()

        self.assertEqual(order.partner_id.id, partner.id)
        self.assertEqual(order.partner_invoice_id.id, billing.id)
        self.assertEqual(order.partner_shipping_id.id, shipping.id)
        self.assertEqual(len(order.order_line), 1)
        self.assertEqual(order.order_line.product_id.default_code, 'guitar-cl-shopify-test-1')
        self.assertEqual(order.order_line.tax_ids.id, tax_23.id)
        self.assertEqual(order.partner_shipping_id.id, shipping.id)

        self.assertFalse(order.fiscal_position_id)
        self.assertEqual(round(order.amount_untaxed, 1), 1723.0)
        self.assertEqual(round(order.amount_tax, 2), 396.29)
        self.assertEqual(round(order.amount_total, 2), 2119.29)

        order.unlink()

        # 3. Process input file with customer's fiscal position and the update_fiscal_positionf flag as True
        self.integration.update_fiscal_position = True

        fiscal_position = self.env['account.fiscal.position'].create({
            'name': 'Fiscal 23 -> 21 Shopify Test',
            'company_id': self.company.id,
            'country_id': self.env.ref('base.pl').id,
            'tax_ids': [(6, 0, [tax_21.id])],
        })

        # Assign FP to the !!!Parent
        partner.parent_id.with_company(self.company).property_account_position_id = fiscal_position.id

        self.assertEqual(
            partner.property_account_position_id.id,
            False,
        )
        self.assertEqual(
            partner.with_company(self.company).property_account_position_id.id,
            fiscal_position.id,
        )

        order = input_file.process_no_job()

        self.assertEqual(order.partner_id.id, partner.id)
        self.assertEqual(order.partner_invoice_id.id, billing.id)
        self.assertEqual(order.partner_shipping_id.id, shipping.id)
        self.assertEqual(len(order.order_line), 1)
        self.assertEqual(order.order_line.product_id.default_code, 'guitar-cl-shopify-test-1')

        self.assertEqual(order.order_line.tax_ids.id, tax_21.id)
        self.assertEqual(order.fiscal_position_id.id, fiscal_position.id)
        self.assertEqual(order.show_update_fpos, False)

        self.assertEqual(round(order.amount_untaxed, 1), 1723.0)
        self.assertEqual(round(order.amount_tax, 2), 361.83)
        self.assertEqual(round(order.amount_total, 2), 2084.83)

        # 4. Process input file with customer's fiscal position and the update_fiscal_positionf flag as False
        self.integration.update_fiscal_position = False
        order.unlink()

        order = input_file.process_no_job()

        self.assertEqual(order.partner_id.id, partner.id)
        self.assertEqual(order.partner_invoice_id.id, billing.id)
        self.assertEqual(order.partner_shipping_id.id, shipping.id)
        self.assertEqual(len(order.order_line), 1)
        self.assertEqual(order.order_line.product_id.default_code, 'guitar-cl-shopify-test-1')

        self.assertEqual(order.order_line.tax_ids.id, tax_23.id)
        self.assertEqual(order.fiscal_position_id.id, fiscal_position.id)
        self.assertEqual(order.show_update_fpos, True)

        self.assertEqual(round(order.amount_untaxed, 1), 1723.0)
        self.assertEqual(round(order.amount_tax, 2), 396.29)
        self.assertEqual(round(order.amount_total, 2), 2119.29)
