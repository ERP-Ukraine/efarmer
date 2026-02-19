# See LICENSE file for full copyright and licensing details.
# flake8: noqa
# pylint: skip-file

import json


STORAGE_STR = """
{
    "product": {
        "10203545100500": {
            "id": "gid://shopify/Product/10203545100500",
            "title": "E-guitar-test_az1u28399",
            "status": "ACTIVE",
            "productType": "",
            "tags": [
                "e-guitar",
                "guitar"
            ],
            "descriptionHtml": "<p>It's just an e-guitar..</p>",
            "options": [
                {
                    "id": "gid://shopify/ProductOption/12558075167012",
                    "name": "Instrument color",
                    "position": 1,
                    "optionValues": [
                        {
                            "id": "gid://shopify/ProductOptionValue/5311845237028",
                            "name": "Gold"
                        },
                        {
                            "id": "gid://shopify/ProductOptionValue/5311845269796",
                            "name": "Bronze"
                        }
                    ]
                },
                {
                    "id": "gid://shopify/ProductOption/12558075199780",
                    "name": "Neck material",
                    "position": 2,
                    "optionValues": [
                        {
                            "id": "gid://shopify/ProductOptionValue/5311845302564",
                            "name": "Boxwood"
                        },
                        {
                            "id": "gid://shopify/ProductOptionValue/5311845335332",
                            "name": "Wood"
                        }
                    ]
                }
            ],
            "metafields": {
                "nodes": [
                    {
                        "id": "gid://shopify/Metafield/44607859654948",
                        "namespace": "custom",
                        "key": "meta1",
                        "value": "e-guitar-meta1-info",
                        "type": "single_line_text_field",
                        "ownerType": "PRODUCT"
                    },
                    {
                        "id": "gid://shopify/Metafield/44607859687716",
                        "namespace": "shopify",
                        "key": "instrument-color",
                        "value": "[\\"gid://shopify/Metaobject/107581145380\\",\\"gid://shopify/Metaobject/208633430308\\"]",
                        "type": "list.metaobject_reference",
                        "ownerType": "PRODUCT"
                    },
                    {
                        "id": "gid://shopify/Metafield/44607859720484",
                        "namespace": "shopify",
                        "key": "neck-material",
                        "value": "[\\"gid://shopify/Metaobject/208633463076\\",\\"gid://shopify/Metaobject/208633495844\\"]",
                        "type": "list.metaobject_reference",
                        "ownerType": "PRODUCT"
                    },
                    {
                        "id": "gid://shopify/Metafield/44608666566948",
                        "namespace": "global",
                        "key": "description_tag",
                        "value": "It's just an e-guitar meta description",
                        "type": "string",
                        "ownerType": "PRODUCT"
                    },
                                        {
                        "id": "gid://shopify/Metafield/44609793327396",
                        "namespace": "global",
                        "key": "title_tag",
                        "value": "E-guitar-test_az1u28399-page-title",
                        "type": "string",
                        "ownerType": "PRODUCT"
                    }
                ]
            },
            "collections": {
                "nodes": [
                    {
                        "id": "gid://shopify/Collection/440312267044",
                        "title": "OUTLET",
                        "description": ""
                    },
                    {
                        "id": "gid://shopify/Collection/440313119012",
                        "title": "Classic",
                        "description": ""
                    }
                ]
            },
            "hasOnlyDefaultVariant": false,
            "category": {
                "id": "gid://shopify/TaxonomyCategory/ae-2-8-7-2-4",
                "name": "Electric Guitars",
                "fullName": "Arts & Entertainment > Hobbies & Creative Arts > Musical Instruments > String Instruments > Guitars > Electric Guitars",
                "parentId": "gid://shopify/TaxonomyCategory/ae-2-8-7-2"
            },
            "variantsCount": {
                "count": 4
            },
            "featuredMedia": null,
            "media": {
                "nodes": []
            },
            "variants": {
                "nodes": [
                    {
                        "id": "gid://shopify/ProductVariant/51158197731620",
                        "product": {
                            "id": "gid://shopify/Product/10203545100500",
                            "hasOnlyDefaultVariant": false,
                            "options": [
                                {
                                    "id": "gid://shopify/ProductOption/12558075167012",
                                    "name": "Instrument color",
                                    "position": 1,
                                    "optionValues": [
                                        {
                                            "id": "gid://shopify/ProductOptionValue/5311845237028",
                                            "name": "Gold"
                                        },
                                        {
                                            "id": "gid://shopify/ProductOptionValue/5311845269796",
                                            "name": "Bronze"
                                        }
                                    ]
                                },
                                {
                                    "id": "gid://shopify/ProductOption/12558075199780",
                                    "name": "Neck material",
                                    "position": 2,
                                    "optionValues": [
                                        {
                                            "id": "gid://shopify/ProductOptionValue/5311845302564",
                                            "name": "Boxwood"
                                        },
                                        {
                                            "id": "gid://shopify/ProductOptionValue/5311845335332",
                                            "name": "Wood"
                                        }
                                    ]
                                }
                            ]
                        },
                        "metafields": {
                            "nodes": []
                        },
                        "availableForSale": true,
                        "sku": "e-guitar-gold-box-test_mdx3xoxx",
                        "barcode": "321321321321",
                        "price": "543.00",
                        "taxable": true,
                        "taxCode": "",
                        "title": "Gold / Boxwood",
                        "inventoryQuantity": 235,
                        "compareAtPrice": "500.00",
                        "inventoryItem": {
                            "id": "gid://shopify/InventoryItem/53159185875236",
                            "inventoryLevels": {
                                "nodes": [
                                    {
                                        "id": "gid://shopify/InventoryLevel/109531201828?inventory_item_id=53159185875236",
                                        "location": {
                                            "id": "gid://shopify/Location/73153839396"
                                        },
                                        "quantities": [
                                            {
                                                "id": "gid://shopify/InventoryQuantity/109531201828?inventory_item_id=53159185875236&name=available",
                                                "name": "available",
                                                "quantity": 112
                                            }
                                        ]
                                    },
                                    {
                                        "id": "gid://shopify/InventoryLevel/116688486692?inventory_item_id=53159185875236",
                                        "location": {
                                            "id": "gid://shopify/Location/80295690532"
                                        },
                                        "quantities": [
                                            {
                                                "id": "gid://shopify/InventoryQuantity/116688486692?inventory_item_id=53159185875236&name=available",
                                                "name": "available",
                                                "quantity": 123
                                            }
                                        ]
                                    }
                                ]
                            },
                            "measurement": {
                                "weight": {
                                    "unit": "KILOGRAMS",
                                    "value": 4.0
                                }
                            },
                            "unitCost": {
                                "amount": "490.0",
                                "currencyCode": "PLN"
                            },
                            "variant": {
                                "id": "gid://shopify/ProductVariant/51158197731620"
                            }
                        },
                        "selectedOptions": [
                            {
                                "name": "Instrument color",
                                "value": "Gold",
                                "optionValue": {
                                    "id": "gid://shopify/ProductOptionValue/5311845237028",
                                    "name": "Gold"
                                }
                            },
                            {
                                "name": "Neck material",
                                "value": "Boxwood",
                                "optionValue": {
                                    "id": "gid://shopify/ProductOptionValue/5311845302564",
                                    "name": "Boxwood"
                                }
                            }
                        ],
                        "media": {
                            "nodes": []
                        }
                    },
                    {
                        "id": "gid://shopify/ProductVariant/51158197764388",
                        "product": {
                            "id": "gid://shopify/Product/10203545100500",
                            "hasOnlyDefaultVariant": false,
                            "options": [
                                {
                                    "id": "gid://shopify/ProductOption/12558075167012",
                                    "name": "Instrument color",
                                    "position": 1,
                                    "optionValues": [
                                        {
                                            "id": "gid://shopify/ProductOptionValue/5311845237028",
                                            "name": "Gold"
                                        },
                                        {
                                            "id": "gid://shopify/ProductOptionValue/5311845269796",
                                            "name": "Bronze"
                                        }
                                    ]
                                },
                                {
                                    "id": "gid://shopify/ProductOption/12558075199780",
                                    "name": "Neck material",
                                    "position": 2,
                                    "optionValues": [
                                        {
                                            "id": "gid://shopify/ProductOptionValue/5311845302564",
                                            "name": "Boxwood"
                                        },
                                        {
                                            "id": "gid://shopify/ProductOptionValue/5311845335332",
                                            "name": "Wood"
                                        }
                                    ]
                                }
                            ]
                        },
                        "metafields": {
                            "nodes": [
                                {
                                    "id": "gid://shopify/Metafield/44607890522404",
                                    "namespace": "custom",
                                    "key": "meta_v1",
                                    "value": "e-guitar-gold-wood-test_mdx3xoxx-meta-v",
                                    "type": "single_line_text_field",
                                    "ownerType": "PRODUCTVARIANT"
                                }
                            ]
                        },
                        "availableForSale": false,
                        "sku": "e-guitar-gold-wood-test_mdx3xoxx",
                        "barcode": "321321321322",
                        "price": "542.00",
                        "taxable": true,
                        "taxCode": "",
                        "title": "Gold / Wood",
                        "inventoryQuantity": 0,
                        "compareAtPrice": "50100.00",
                        "inventoryItem": {
                            "id": "gid://shopify/InventoryItem/53159185908004",
                            "inventoryLevels": {
                                "nodes": [
                                    {
                                        "id": "gid://shopify/InventoryLevel/109531201828?inventory_item_id=53159185908004",
                                        "location": {
                                            "id": "gid://shopify/Location/73153839396"
                                        },
                                        "quantities": [
                                            {
                                                "id": "gid://shopify/InventoryQuantity/109531201828?inventory_item_id=53159185908004&name=available",
                                                "name": "available",
                                                "quantity": 0
                                            }
                                        ]
                                    },
                                    {
                                        "id": "gid://shopify/InventoryLevel/116688486692?inventory_item_id=53159185908004",
                                        "location": {
                                            "id": "gid://shopify/Location/80295690532"
                                        },
                                        "quantities": [
                                            {
                                                "id": "gid://shopify/InventoryQuantity/116688486692?inventory_item_id=53159185908004&name=available",
                                                "name": "available",
                                                "quantity": 0
                                            }
                                        ]
                                    }
                                ]
                            },
                            "measurement": {
                                "weight": {
                                    "unit": "KILOGRAMS",
                                    "value": 4.0
                                }
                            },
                            "unitCost": {
                                "amount": "485.0",
                                "currencyCode": "PLN"
                            },
                            "variant": {
                                "id": "gid://shopify/ProductVariant/51158197764388"
                            }
                        },
                        "selectedOptions": [
                            {
                                "name": "Instrument color",
                                "value": "Gold",
                                "optionValue": {
                                    "id": "gid://shopify/ProductOptionValue/5311845237028",
                                    "name": "Gold"
                                }
                            },
                            {
                                "name": "Neck material",
                                "value": "Wood",
                                "optionValue": {
                                    "id": "gid://shopify/ProductOptionValue/5311845335332",
                                    "name": "Wood"
                                }
                            }
                        ],
                        "media": {
                            "nodes": []
                        }
                    },
                    {
                        "id": "gid://shopify/ProductVariant/51158197797156",
                        "product": {
                            "id": "gid://shopify/Product/10203545100500",
                            "hasOnlyDefaultVariant": false,
                            "options": [
                                {
                                    "id": "gid://shopify/ProductOption/12558075167012",
                                    "name": "Instrument color",
                                    "position": 1,
                                    "optionValues": [
                                        {
                                            "id": "gid://shopify/ProductOptionValue/5311845237028",
                                            "name": "Gold"
                                        },
                                        {
                                            "id": "gid://shopify/ProductOptionValue/5311845269796",
                                            "name": "Bronze"
                                        }
                                    ]
                                },
                                {
                                    "id": "gid://shopify/ProductOption/12558075199780",
                                    "name": "Neck material",
                                    "position": 2,
                                    "optionValues": [
                                        {
                                            "id": "gid://shopify/ProductOptionValue/5311845302564",
                                            "name": "Boxwood"
                                        },
                                        {
                                            "id": "gid://shopify/ProductOptionValue/5311845335332",
                                            "name": "Wood"
                                        }
                                    ]
                                }
                            ]
                        },
                        "metafields": {
                            "nodes": [
                                {
                                    "id": "gid://shopify/Metafield/44607899762980",
                                    "namespace": "custom",
                                    "key": "meta_v1",
                                    "value": "e-guitar-bronze-box-test_mdx3xoxx-meta-v",
                                    "type": "single_line_text_field",
                                    "ownerType": "PRODUCTVARIANT"
                                }
                            ]
                        },
                        "availableForSale": false,
                        "sku": "e-guitar-bronze-box-test_mdx3xoxx",
                        "barcode": "321321321323",
                        "price": "541.00",
                        "taxable": true,
                        "taxCode": "",
                        "title": "Bronze / Boxwood",
                        "inventoryQuantity": 0,
                        "compareAtPrice": "502.00",
                        "inventoryItem": {
                            "id": "gid://shopify/InventoryItem/53159185940772",
                            "inventoryLevels": {
                                "nodes": [
                                    {
                                        "id": "gid://shopify/InventoryLevel/109531201828?inventory_item_id=53159185940772",
                                        "location": {
                                            "id": "gid://shopify/Location/73153839396"
                                        },
                                        "quantities": [
                                            {
                                                "id": "gid://shopify/InventoryQuantity/109531201828?inventory_item_id=53159185940772&name=available",
                                                "name": "available",
                                                "quantity": 0
                                            }
                                        ]
                                    },
                                    {
                                        "id": "gid://shopify/InventoryLevel/116688486692?inventory_item_id=53159185940772",
                                        "location": {
                                            "id": "gid://shopify/Location/80295690532"
                                        },
                                        "quantities": [
                                            {
                                                "id": "gid://shopify/InventoryQuantity/116688486692?inventory_item_id=53159185940772&name=available",
                                                "name": "available",
                                                "quantity": 0
                                            }
                                        ]
                                    }
                                ]
                            },
                            "measurement": {
                                "weight": {
                                    "unit": "KILOGRAMS",
                                    "value": 4.0
                                }
                            },
                            "unitCost": {
                                "amount": "480.0",
                                "currencyCode": "PLN"
                            },
                            "variant": {
                                "id": "gid://shopify/ProductVariant/51158197797156"
                            }
                        },
                        "selectedOptions": [
                            {
                                "name": "Instrument color",
                                "value": "Bronze",
                                "optionValue": {
                                    "id": "gid://shopify/ProductOptionValue/5311845269796",
                                    "name": "Bronze"
                                }
                            },
                            {
                                "name": "Neck material",
                                "value": "Boxwood",
                                "optionValue": {
                                    "id": "gid://shopify/ProductOptionValue/5311845302564",
                                    "name": "Boxwood"
                                }
                            }
                        ],
                        "media": {
                            "nodes": []
                        }
                    },
                    {
                        "id": "gid://shopify/ProductVariant/51158197829924",
                        "product": {
                            "id": "gid://shopify/Product/10203545100500",
                            "hasOnlyDefaultVariant": false,
                            "options": [
                                {
                                    "id": "gid://shopify/ProductOption/12558075167012",
                                    "name": "Instrument color",
                                    "position": 1,
                                    "optionValues": [
                                        {
                                            "id": "gid://shopify/ProductOptionValue/5311845237028",
                                            "name": "Gold"
                                        },
                                        {
                                            "id": "gid://shopify/ProductOptionValue/5311845269796",
                                            "name": "Bronze"
                                        }
                                    ]
                                },
                                {
                                    "id": "gid://shopify/ProductOption/12558075199780",
                                    "name": "Neck material",
                                    "position": 2,
                                    "optionValues": [
                                        {
                                            "id": "gid://shopify/ProductOptionValue/5311845302564",
                                            "name": "Boxwood"
                                        },
                                        {
                                            "id": "gid://shopify/ProductOptionValue/5311845335332",
                                            "name": "Wood"
                                        }
                                    ]
                                }
                            ]
                        },
                        "metafields": {
                            "nodes": [
                                {
                                    "id": "gid://shopify/Metafield/44607924306212",
                                    "namespace": "custom",
                                    "key": "meta_v1",
                                    "value": "e-guitar-gold-wood-test_mdx3xoxx-meta-v",
                                    "type": "single_line_text_field",
                                    "ownerType": "PRODUCTVARIANT"
                                }
                            ]
                        },
                        "availableForSale": false,
                        "sku": "e-guitar-bronze-wood-test_mdx3xoxx",
                        "barcode": "321321321324",
                        "price": "539.00",
                        "taxable": true,
                        "taxCode": "",
                        "title": "Bronze / Wood",
                        "inventoryQuantity": 0,
                        "compareAtPrice": "503.00",
                        "inventoryItem": {
                            "id": "gid://shopify/InventoryItem/53159185973540",
                            "inventoryLevels": {
                                "nodes": [
                                    {
                                        "id": "gid://shopify/InventoryLevel/109531201828?inventory_item_id=53159185973540",
                                        "location": {
                                            "id": "gid://shopify/Location/73153839396"
                                        },
                                        "quantities": [
                                            {
                                                "id": "gid://shopify/InventoryQuantity/109531201828?inventory_item_id=53159185973540&name=available",
                                                "name": "available",
                                                "quantity": 0
                                            }
                                        ]
                                    },
                                    {
                                        "id": "gid://shopify/InventoryLevel/116688486692?inventory_item_id=53159185973540",
                                        "location": {
                                            "id": "gid://shopify/Location/80295690532"
                                        },
                                        "quantities": [
                                            {
                                                "id": "gid://shopify/InventoryQuantity/116688486692?inventory_item_id=53159185973540&name=available",
                                                "name": "available",
                                                "quantity": 0
                                            }
                                        ]
                                    }
                                ]
                            },
                            "measurement": {
                                "weight": {
                                    "unit": "KILOGRAMS",
                                    "value": 4.0
                                }
                            },
                            "unitCost": {
                                "amount": "475.0",
                                "currencyCode": "PLN"
                            },
                            "variant": {
                                "id": "gid://shopify/ProductVariant/51158197829924"
                            }
                        },
                        "selectedOptions": [
                            {
                                "name": "Instrument color",
                                "value": "Bronze",
                                "optionValue": {
                                    "id": "gid://shopify/ProductOptionValue/5311845269796",
                                    "name": "Bronze"
                                }
                            },
                            {
                                "name": "Neck material",
                                "value": "Wood",
                                "optionValue": {
                                    "id": "gid://shopify/ProductOptionValue/5311845335332",
                                    "name": "Wood"
                                }
                            }
                        ],
                        "media": {
                            "nodes": []
                        }
                    }
                ]
            }
        }
    },
    "order": {
        "100500": {
            "id": "gid://shopify/Order/100500",
            "name": "#1166",
            "sourceName": "shopify_draft_order",
            "email": "przecietny-kowalski222@mail.pl",
            "phone": "+48123234456",
            "confirmed": true,
            "cancelReason": null,
            "cancelledAt": null,
            "closedAt": "2024-10-08T12:07:59Z",
            "createdAt": "2024-10-08T12:03:31Z",
            "updatedAt": "2024-10-08T12:07:59Z",
            "processedAt": "2024-10-08T12:03:30Z",
            "displayFulfillmentStatus": "FULFILLED",
            "displayFinancialStatus": "PAID",
            "returnStatus": "NO_RETURN",
            "customerLocale": "en",
            "taxesIncluded": false,
            "taxExempt": false,
            "totalWeight": "19000",
            "confirmationNumber": "ID2RFRKPX",
            "discountCode": null,
            "discountCodes": [],
            "currencyCode": "PLN",
            "presentmentCurrencyCode": "PLN",
            "requiresShipping": true,
            "note": "Just note from customer",
            "fullyPaid": true,
            "fulfillable": false,
            "paymentGatewayNames": [
                "manual_in_shopify_test"
            ],
            "tags": [
                "ttag1",
                "ttag2"
            ],
            "shippingLines": {
                "nodes": []
            },
            "taxLines": [
                {
                    "rate": 0.23,
                    "ratePercentage": 23.0,
                    "source": "Shopify",
                    "title": "PL VATt"
                }
            ],
            "shippingLine": null,
            "publication": null,
            "risk": {
                "assessments": [
                    {
                        "facts": [
                            {
                                "description": "Numer CVV (CVV) jest niedostępny",
                                "sentiment": "NEUTRAL"
                            },
                            {
                                "description": "Adres rozliczeniowy lub adres karty kredytowej nie był dostępny",
                                "sentiment": "NEUTRAL"
                            },
                            {
                                "description": "Kod pocztowy adresu rozliczeniowego nie jest dostępny dla ...",
                                "sentiment": "NEUTRAL"
                            },
                            {
                                "description": "Wykorzystano metodę płatności inną niż karta kredytowa",
                                "sentiment": "NEUTRAL"
                            },
                            {
                                "description": "Lokalizacja adresu IP użytego do złożenia zamówienia to Warsaw ...",
                                "sentiment": "NEUTRAL"
                            },
                            {
                                "description": "Odległość między adresem wysyłki a lokalizacją nie jest dostępna",
                                "sentiment": "NEUTRAL"
                            },
                            {
                                "description": "Wykonano 1 próbę płatności",
                                "sentiment": "POSITIVE"
                            },
                            {
                                "description": "Kraj rozliczenia pasuje do kraju, z którego zamówienie zostało złożone",
                                "sentiment": "POSITIVE"
                            }
                        ],
                        "riskLevel": "NONE"
                    }
                ],
                "recommendation": "NONE"
            },
            "transactions": [
                {
                    "id": "gid://shopify/OrderTransaction/10679267000000",
                    "order": {
                        "id": "gid://shopify/Order/100500"
                    },
                    "paymentId": "rC16cqp2Dhpjj5XRS3NR7m11q",
                    "kind": "SALE",
                    "status": "SUCCESS",
                    "gateway": "manual_in_shopify_test",
                    "formattedGateway": "Manual",
                    "amountSet": {
                        "presentmentMoney": {
                            "amount": "147.58",
                            "currencyCode": "PLN"
                        },
                        "shopMoney": {
                            "amount": "147.58",
                            "currencyCode": "PLN"
                        }
                    },
                    "parentTransaction": null,
                    "processedAt": "2024-10-08T12:03:31Z"
                }
            ],
            "fulfillmentOrders": {
                "nodes": [
                    {
                        "id": "gid://shopify/FulfillmentOrder/10575833104676",
                        "orderId": "gid://shopify/Order/100500",
                        "status": "CLOSED",
                        "lineItems": {
                            "nodes": [
                                {
                                    "id": "gid://shopify/FulfillmentOrderLineItem/31136387170596",
                                    "totalQuantity": 2,
                                    "remainingQuantity": 0,
                                    "sku": "gtp3-ref-2",
                                    "lineItem": {
                                        "id": "gid://shopify/LineItem/31108738842916"
                                    }
                                },
                                {
                                    "id": "gid://shopify/FulfillmentOrderLineItem/31136387203364",
                                    "totalQuantity": 3,
                                    "remainingQuantity": 0,
                                    "sku": "guit1-sku-bl",
                                    "lineItem": {
                                        "id": "gid://shopify/LineItem/31108738875684"
                                    }
                                }
                            ]
                        },
                        "assignedLocation": {
                            "location": {
                                "id": "gid://shopify/Location/73153839396"
                            }
                        },
                        "deliveryMethod": {
                            "id": "gid://shopify/DeliveryMethod/4932258562340",
                            "presentedName": "shippinggg",
                            "methodType": "SHIPPING",
                            "serviceCode": "custom",
                            "sourceReference": null
                        }
                    }
                ]
            },
            "fulfillments": [
                {
                    "id": "gid://shopify/Fulfillment/5413320589604",
                    "name": "#1166-F2",
                    "status": "SUCCESS",
                    "displayStatus": "FULFILLED",
                    "totalQuantity": 3,
                    "trackingInfo": [
                        {
                            "number": "track-num2",
                            "company": "AGS",
                            "url": "https://tracking.agsystems.com/"
                        }
                    ],
                    "order": {
                        "id": "gid://shopify/Order/100500"
                    },
                    "fulfillmentOrders": {
                        "nodes": [
                            {
                                "id": "gid://shopify/FulfillmentOrder/10575833104676"
                            }
                        ]
                    },
                    "location": {
                        "id": "gid://shopify/Location/73153839396"
                    },
                    "fulfillmentLineItems": {
                        "nodes": [
                            {
                                "id": "gid://shopify/FulfillmentLineItem/13449096266020",
                                "quantity": 3,
                                "lineItem": {
                                    "id": "gid://shopify/LineItem/31108738875684",
                                    "sku": "guit1-sku-bl",
                                    "quantity": 3,
                                    "nonFulfillableQuantity": 0,
                                    "variant": {
                                        "id": "gid://shopify/ProductVariant/47738503495000",
                                        "product": {
                                            "id": "gid://shopify/Product/8991067530000"
                                        }
                                    }
                                }
                            }
                        ]
                    },
                    "service": {
                        "id": "gid://shopify/FulfillmentService/manual",
                        "handle": "manual",
                        "serviceName": "Ręcznie",
                        "trackingSupport": false,
                        "type": "MANUAL"
                    },
                    "updatedAt": "2024-10-08T12:07:59Z"
                },
                {
                    "id": "gid://shopify/Fulfillment/5413320294692",
                    "name": "#1166-F1",
                    "status": "SUCCESS",
                    "displayStatus": "FULFILLED",
                    "totalQuantity": 2,
                    "trackingInfo": [
                        {
                            "number": "track-num1",
                            "company": "4PX",
                            "url": "http://track.4px.com/query/track-num1"
                        }
                    ],
                    "order": {
                        "id": "gid://shopify/Order/100500"
                    },
                    "fulfillmentOrders": {
                        "nodes": [
                            {
                                "id": "gid://shopify/FulfillmentOrder/10575833104676"
                            }
                        ]
                    },
                    "location": {
                        "id": "gid://shopify/Location/73153839396"
                    },
                    "fulfillmentLineItems": {
                        "nodes": [
                            {
                                "id": "gid://shopify/FulfillmentLineItem/13449095938340",
                                "quantity": 2,
                                "lineItem": {
                                    "id": "gid://shopify/LineItem/31108738842916",
                                    "sku": "gtp3-ref-2",
                                    "quantity": 2,
                                    "nonFulfillableQuantity": 0,
                                    "variant": {
                                        "id": "gid://shopify/ProductVariant/49620724449000",
                                        "product": {
                                            "id": "gid://shopify/Product/9154587918000"
                                        }
                                    }
                                }
                            }
                        ]
                    },
                    "service": {
                        "id": "gid://shopify/FulfillmentService/manual",
                        "handle": "manual",
                        "serviceName": "Ręcznie",
                        "trackingSupport": false,
                        "type": "MANUAL"
                    },
                    "updatedAt": "2024-10-08T12:07:41Z"
                }
            ],
            "currentTotalPriceSet": {
                "presentmentMoney": {
                    "amount": "2147.58",
                    "currencyCode": "PLN"
                },
                "shopMoney": {
                    "amount": "2147.58",
                    "currencyCode": "PLN"
                }
            },
            "billingAddress": null,
            "shippingAddress": null,
            "billingAddressMatchesShippingAddress": true,
            "customer": {
                "id": "gid://shopify/Customer/6670178025000",
                "email": "przecietny-kowalski@mail.pl",
                "firstName": "Przeciętny",
                "lastName": "Kowalski",
                "displayName": "Przeciętny Kowalski",
                "phone": "+48123234456",
                "locale": "pl",
                "createdAt": "2022-11-09T18:09:56Z",
                "updatedAt": "2025-08-27T14:39:09Z",
                "tags": [],
                "addresses": [
                    {
                        "id": "gid://shopify/MailingAddress/8941943193892?model_name=CustomerAddress",
                        "address1": "Księdza Pawła Lexa 100",
                        "address2": "",
                        "city": "Ruda Śląska",
                        "company": "Przeciętny COmpany",
                        "country": "Poland",
                        "countryCodeV2": "PL",
                        "firstName": "Przeciętny",
                        "lastName": "Kowalski",
                        "phone": "+48123234345",
                        "province": null,
                        "provinceCode": null,
                        "zip": "01-123",
                        "formatted": [
                            "Przeciętny COmpany",
                            "Księdza Pawła Lexa 100",
                            "01-123 Ruda Śląska",
                            "Polska"
                        ]
                    },
                    {
                        "id": "gid://shopify/MailingAddress/9180037251364?model_name=CustomerAddress",
                        "address1": "Księdza Pawła Lexa 100",
                        "address2": null,
                        "city": "Ruda Śląska",
                        "company": "Przeciętny COmpany",
                        "country": "Poland",
                        "countryCodeV2": "PL",
                        "firstName": "Przeciętny",
                        "lastName": "Kowalski",
                        "phone": "+48123234346",
                        "province": null,
                        "provinceCode": null,
                        "zip": "01-123",
                        "formatted": [
                            "Przeciętny COmpany",
                            "Księdza Pawła Lexa 100",
                            "01-123 Ruda Śląska",
                            "Polska"
                        ]
                    },
                    {
                        "id": "gid://shopify/MailingAddress/9905196630308?model_name=CustomerAddress",
                        "address1": "Górna 22",
                        "address2": null,
                        "city": "Warszawa",
                        "company": null,
                        "country": "Poland",
                        "countryCodeV2": "PL",
                        "firstName": "Przeciętny",
                        "lastName": "Kowalski",
                        "phone": null,
                        "province": null,
                        "provinceCode": null,
                        "zip": "01-123",
                        "formatted": [
                            "Górna 22",
                            "01-123 Warszawa",
                            "Polska"
                        ]
                    }
                ],
                "defaultAddress": {
                    "id": "gid://shopify/MailingAddress/9180037251364?model_name=CustomerAddress"
                }
            },
            "lineItems": {
                "nodes": [
                    {
                        "id": "gid://shopify/LineItem/31108738842916",
                        "name": "Guitar Pro3 - White",
                        "quantity": 2,
                        "isGiftCard": false,
                        "currentQuantity": 2,
                        "taxable": true,
                        "originalUnitPriceSet": {
                            "presentmentMoney": {
                                "amount": "123.0",
                                "currencyCode": "PLN"
                            },
                            "shopMoney": {
                                "amount": "123.0",
                                "currencyCode": "PLN"
                            }
                        },
                        "discountAllocations": [],
                        "taxLines": [
                            {
                                "rate": 0.23,
                                "ratePercentage": 23.0,
                                "source": "Shopify",
                                "title": "PL VATt",
                                "priceSet": {
                                    "presentmentMoney": {
                                        "amount": "56.58",
                                        "currencyCode": "PLN"
                                    },
                                    "shopMoney": {
                                        "amount": "56.58",
                                        "currencyCode": "PLN"
                                    }
                                }
                            }
                        ],
                        "variant": {
                            "product": {
                                "id": "gid://shopify/Product/9154587918000"
                            },
                            "id": "gid://shopify/ProductVariant/49620724449000",
                            "sku": "gtp3-ref-2",
                            "title": "White"
                        }
                    },
                    {
                        "id": "gid://shopify/LineItem/31108738875684",
                        "name": "Guitar1 - Black",
                        "quantity": 3,
                        "isGiftCard": false,
                        "currentQuantity": 3,
                        "taxable": true,
                        "originalUnitPriceSet": {
                            "presentmentMoney": {
                                "amount": "500.0",
                                "currencyCode": "PLN"
                            },
                            "shopMoney": {
                                "amount": "500.0",
                                "currencyCode": "PLN"
                            }
                        },
                        "discountAllocations": [],
                        "taxLines": [
                            {
                                "rate": 0.23,
                                "ratePercentage": 23.0,
                                "source": "Shopify",
                                "title": "PL VATt",
                                "priceSet": {
                                    "presentmentMoney": {
                                        "amount": "345.0",
                                        "currencyCode": "PLN"
                                    },
                                    "shopMoney": {
                                        "amount": "345.0",
                                        "currencyCode": "PLN"
                                    }
                                }
                            }
                        ],
                        "variant": {
                            "product": {
                                "id": "gid://shopify/Product/8991067530000"
                            },
                            "id": "gid://shopify/ProductVariant/47738503495000",
                            "sku": "guit1-sku-bl",
                            "title": "Black"
                        }
                    }
                ]
            }
        },
        "100510": {
            "id": "gid://shopify/Order/100510",
            "name": "#1169",
            "sourceName": "shopify_draft_order",
            "email": "j.hatf.shopify.test@myshopify.test.com",
            "phone": null,
            "confirmed": true,
            "cancelReason": null,
            "cancelledAt": null,
            "closedAt": null,
            "createdAt": "2024-10-24T09:24:24Z",
            "updatedAt": "2024-11-25T14:00:50Z",
            "processedAt": "2024-10-24T09:24:24Z",
            "displayFulfillmentStatus": "UNFULFILLED",
            "displayFinancialStatus": "PAID",
            "returnStatus": "NO_RETURN",
            "customerLocale": "en",
            "taxesIncluded": false,
            "taxExempt": false,
            "totalWeight": "3000",
            "confirmationNumber": "TYT0D85KM",
            "discountCode": null,
            "discountCodes": [],
            "currencyCode": "PLN",
            "presentmentCurrencyCode": "PLN",
            "requiresShipping": true,
            "note": null,
            "fullyPaid": true,
            "fulfillable": true,
            "paymentGatewayNames": [
                "manual"
            ],
            "tags": [],
            "shippingLines": {
                "nodes": []
            },
            "taxLines": [
                {
                    "rate": 0.23,
                    "ratePercentage": 23.0,
                    "source": "Shopify",
                    "title": "PL VATt"
                }
            ],
            "shippingLine": null,
            "publication": null,
            "risk": {
                "assessments": [
                    {
                        "facts": [
                            {
                                "description": "Numer CVV (CVV) jest niedostępny",
                                "sentiment": "NEUTRAL"
                            },
                            {
                                "description": "Adres rozliczeniowy lub adres karty kredytowej nie był dostępny",
                                "sentiment": "NEUTRAL"
                            },
                            {
                                "description": "Wykorzystano metodę płatności inną niż karta kredytowa",
                                "sentiment": "NEUTRAL"
                            },
                            {
                                "description": "Lokalizacja adresu IP użytego do złożenia zamówienia to Warsaw ..",
                                "sentiment": "NEUTRAL"
                            },
                            {
                                "description": "Wykonano 1 próbę płatności",
                                "sentiment": "POSITIVE"
                            },
                            {
                                "description": "Adres wysyłki znajduje się w odległości 51 km od lokalizacji adresu IP",
                                "sentiment": "POSITIVE"
                            },
                            {
                                "description": "Kraj rozliczenia pasuje do kraju, z którego zamówienie zostało złożone",
                                "sentiment": "POSITIVE"
                            }
                        ],
                        "riskLevel": "NONE"
                    }
                ],
                "recommendation": "NONE"
            },
            "transactions": [
                {
                    "id": "gid://shopify/OrderTransaction/10706450678052",
                    "order": {
                        "id": "gid://shopify/Order/100510"
                    },
                    "paymentId": "r7GTHvjt4s4sV2KSJqbeaezh7",
                    "kind": "SALE",
                    "status": "SUCCESS",
                    "gateway": "manual_in_shopify_test",
                    "formattedGateway": "Manual",
                    "amountSet": {
                        "presentmentMoney": {
                            "amount": "2119.29",
                            "currencyCode": "PLN"
                        },
                        "shopMoney": {
                            "amount": "2119.29",
                            "currencyCode": "PLN"
                        }
                    },
                    "parentTransaction": null,
                    "processedAt": "2024-10-24T09:24:24Z"
                }
            ],
            "fulfillmentOrders": {
                "nodes": [
                    {
                        "id": "gid://shopify/FulfillmentOrder/10597238340000",
                        "orderId": "gid://shopify/Order/100510",
                        "status": "OPEN",
                        "lineItems": {
                            "nodes": [
                                {
                                    "id": "gid://shopify/FulfillmentOrderLineItem/31181893697828",
                                    "totalQuantity": 1,
                                    "remainingQuantity": 1,
                                    "sku": "guitar-cl-sp-test-1",
                                    "lineItem": {
                                        "id": "gid://shopify/LineItem/31153178968356"
                                    }
                                }
                            ]
                        },
                        "assignedLocation": {
                            "location": {
                                "id": "gid://shopify/Location/73153839000"
                            }
                        },
                        "deliveryMethod": {
                            "id": "gid://shopify/DeliveryMethod/4952923930916",
                            "presentedName": "Shipping",
                            "methodType": "SHIPPING",
                            "serviceCode": "custom",
                            "sourceReference": null
                        }
                    }
                ]
            },
            "fulfillments": [],
            "currentTotalPriceSet": {
                "presentmentMoney": {
                    "amount": "2119.29",
                    "currencyCode": "PLN"
                },
                "shopMoney": {
                    "amount": "2119.29",
                    "currencyCode": "PLN"
                }
            },
            "billingAddress": {
                "id": "gid://shopify/MailingAddress/22632603812132?model_name=Address",
                "address1": "Trojanowska 71",
                "address2": null,
                "city": "Sochaczew",
                "company": "J. Hat Co",
                "country": "Poland",
                "countryCodeV2": "PL",
                "firstName": "James",
                "lastName": "Hatf",
                "phone": "+48534612001",
                "province": null,
                "provinceCode": null,
                "zip": "96-500",
                "formatted": [
                    "J. Hat Co",
                    "Trojanowska 71",
                    "96-500 Sochaczew",
                    "Polska"
                ]
            },
            "shippingAddress": {
                "id": "gid://shopify/MailingAddress/22632603779364?model_name=Address",
                "address1": "Trojanowska 72",
                "address2": null,
                "city": "Sochaczew",
                "company": "J. Hat Co",
                "country": "Poland",
                "countryCodeV2": "PL",
                "firstName": "James",
                "lastName": "Hatf",
                "phone": "+48534612001",
                "province": null,
                "provinceCode": null,
                "zip": "96-500",
                "formatted": [
                    "J. Hat Co",
                    "Trojanowska 72",
                    "96-500 Sochaczew",
                    "Polska"
                ]
            },
            "billingAddressMatchesShippingAddress": false,
            "customer": {
                "id": "gid://shopify/Customer/22299318910000",
                "email": "j.hatf.shopify.test@myshopify.test.com",
                "firstName": "James",
                "lastName": "Hatf",
                "displayName": "James Hatf",
                "phone": "+48534612001",
                "locale": "pl",
                "createdAt": "2024-10-24T09:23:57Z",
                "updatedAt": "2025-06-05T08:19:26Z",
                "tags": [],
                "addresses": [
                    {
                        "id": "gid://shopify/MailingAddress/32514576089380?model_name=CustomerAddress",
                        "address1": "Trojanowska 71",
                        "address2": "",
                        "city": "Sochaczew",
                        "company": "J. Hat Co ",
                        "country": "Poland",
                        "countryCodeV2": "PL",
                        "firstName": "James",
                        "lastName": "Hatf",
                        "phone": "+48534612001",
                        "province": null,
                        "provinceCode": null,
                        "zip": "96-500",
                        "formatted": [
                            "J. Hat Co ",
                            "Trojanowska 71",
                            "96-500 Sochaczew",
                            "Polska"
                        ]
                    },
                                        {
                        "id": "gid://shopify/MailingAddress/32514576089381?model_name=CustomerAddress",
                        "address1": "Trojanowska 72",
                        "address2": "",
                        "city": "Sochaczew",
                        "company": "J. Hat Co ",
                        "country": "Poland",
                        "countryCodeV2": "PL",
                        "firstName": "James",
                        "lastName": "Hatf",
                        "phone": "+48534612001",
                        "province": null,
                        "provinceCode": null,
                        "zip": "96-500",
                        "formatted": [
                            "J. Hat Co ",
                            "Trojanowska 72",
                            "96-500 Sochaczew",
                            "Polska"
                        ]
                    }
                ],
                "defaultAddress": {
                    "id": "gid://shopify/MailingAddress/32514576089380?model_name=CustomerAddress"
                }
            },
            "lineItems": {
                "nodes": [
                    {
                        "id": "gid://shopify/LineItem/31153178968356",
                        "name": "Guitar classic SP-t",
                        "quantity": 1,
                        "isGiftCard": false,
                        "currentQuantity": 1,
                        "taxable": true,
                        "originalUnitPriceSet": {
                            "presentmentMoney": {
                                "amount": "1723.0",
                                "currencyCode": "PLN"
                            },
                            "shopMoney": {
                                "amount": "1723.0",
                                "currencyCode": "PLN"
                            }
                        },
                        "discountAllocations": [],
                        "taxLines": [
                            {
                                "rate": 0.23,
                                "ratePercentage": 23.0,
                                "source": "Shopify",
                                "title": "PL VATt",
                                "priceSet": {
                                    "presentmentMoney": {
                                        "amount": "396.29",
                                        "currencyCode": "PLN"
                                    },
                                    "shopMoney": {
                                        "amount": "396.29",
                                        "currencyCode": "PLN"
                                    }
                                }
                            }
                        ],
                        "variant": {
                            "product": {
                                "id": "gid://shopify/Product/9912501730000"
                            },
                            "id": "gid://shopify/ProductVariant/50025308420000",
                            "sku": "guitar-cl-sp-test-1",
                            "title": "Default Title"
                        }
                    }
                ]
            }
        }
    }
}
"""


STORAGE = json.loads(STORAGE_STR)
