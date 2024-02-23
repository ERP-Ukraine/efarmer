product_pt_1 = """
{
        "id": 1111,
        "title": "Test Product Template 1",
        "body_html": "<p>test 1</p>",
        "vendor": "Odoo",
        "product_type": "",
        "created_at": "2023-03-26T15:35:17+02:00",
        "handle": "test product 1",
        "updated_at": "2023-08-03T12:14:44+02:00",
        "published_at": "2023-03-26T15:35:17+02:00",
        "template_suffix": null,
        "status": "active",
        "published_scope": "web",
        "tags": "",
        "admin_graphql_api_id": "gid://shopify/Product/1111",
        "variants": [
            {
                "id": 2222,
                "product_id": 1111,
                "title": "Test Product 1",
                "price": "15.0",
                "sku": "default_code_1",
                "position": 1,
                "inventory_policy": "deny",
                "compare_at_price": null,
                "fulfillment_service": "manual",
                "inventory_management": "Odoo",
                "option1": "Default Title",
                "option2": null,
                "option3": null,
                "created_at": "2023-03-26T15:35:17+02:00",
                "updated_at": "2023-08-03T12:14:44+02:00",
                "taxable": true,
                "barcode": "",
                "grams": 0,
                "image_id": 40084032454870,
                "weight": 0.0,
                "weight_unit": "kg",
                "inventory_item_id": 46208571408598,
                "inventory_quantity": 0,
                "old_inventory_quantity": 0,
                "requires_shipping": true,
                "admin_graphql_api_id": "gid://odoo/ProductVariant/2222"
            }
        ],
        "options": [
            {
                "id": 10218651418838,
                "product_id": 1111,
                "name": "Title",
                "position": 1,
                "values": [
                    "Default Title"
                ]
            }
        ],
        "images": [
            {
                "id": 40084032454870,
                "product_id": 1111,
                "position": 1,
                "created_at": "2023-08-03T12:14:44+02:00",
                "updated_at": "2023-08-03T12:14:44+02:00",
                "alt": null,
                "width": 1000,
                "height": 657,
                "src": "https://cdn.odoo.com/s/files/1/0658/3251/7846",
                "variant_ids": [
                    2222
                ],
                "admin_graphql_api_id": "gid://odoo/ProductImage/40084032454870"
            }
        ],
        "image": {
            "id": 40084032454870,
            "product_id": 1111,
            "position": 1,
            "created_at": "2023-08-03T12:14:44+02:00",
            "updated_at": "2023-08-03T12:14:44+02:00",
            "alt": null,
            "width": 1000,
            "height": 657,
            "src": "https://cdn.odoo.com/s/files/1/0658/3251/7846/",
            "variant_ids": [
                44105239953622
            ],
            "admin_graphql_api_id": "gid://shopify/ProductImage/40084032454870"
        }
    }
"""

pt_1 = '''{
    "id": 1111,
    "title": "Test Product Template 2",
    "body_html": "<p>test 1</p>",
    "vendor": "Odoo Connector",
    "product_type": "",
    "created_at": "2023-03-26T15:35:17+02:00",
    "handle": "avo6",
    "updated_at": "2023-08-03T12:14:44+02:00",
    "published_at": "2023-03-26T15:35:17+02:00",
    "template_suffix": null,
    "status": "active",
    "published_scope": "web"
}'''

pt_pp_1 = '''{
    "id": 2222,
    "product_id": 1111,
    "title": "Test Product Variant 2",
    "price": "15.0",
    "sku": "default_code_1",
    "position": 1,
    "inventory_policy": "deny",
    "compare_at_price": null,
    "fulfillment_service": "manual",
    "inventory_management": "Odoo",
    "option1": "Default Title",
    "option2": null,
    "option3": null,
    "created_at": "2023-03-26T15:35:17+02:00",
    "updated_at": "2023-08-03T12:14:44+02:00",
    "taxable": true,
    "barcode": "",
    "grams": 0,
    "image_id": 40084032454870,
    "weight": 0.0,
    "weight_unit": "kg",
    "inventory_item_id": 46208571408598,
    "inventory_quantity": 0,
    "old_inventory_quantity": 0,
    "requires_shipping": true,
    "admin_graphql_api_id": "gid://odoo/ProductVariant/2222"
}'''
