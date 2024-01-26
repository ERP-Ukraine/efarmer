==========================
 Quick configuration guide
==========================

|

1. Install the Odoo Shopify Connector on your Odoo server – How to install in `Odoo.sh <https://youtu.be/1kZtC7S-TNA>`__.

|

2. Then follow the steps from this video to make an initial configuration - `watch video <https://youtu.be/BgPB4dhKEQE>`__.

|

3. As our connector is using queue_job from OCA, you need to make sure also to properly configure your Odoo instance. Specifically check that you have below in your odoo.conf file:

   - Make sure that number of workers is 2 and higher (e.g. ``workers = 4``)
   - Make sure queue_job module is added to server wide modules (e.g. ``server_wide_modules = web,queue_job,integration,integration_shopify``)
   - Add the following lines specific to queue_job to identify amount of channels that will be used for it`

    | ``workers = 2 ; set here amount of workers higher than 1``
    | ``server_wide_modules = web,queue_job,integration,integration_shopify ; add queue_job to server wide modules``
    | ``[queue_job]``
    | ``channels = root:1``

|

4. Special note for deploying to odoo.sh (`video <https://youtu.be/1kZtC7S-TNA>`__):

   -  Config file can be found when entering shell in the following location "/home/odoo/.config/odoo/odoo.conf". Add there the following configs:


    | ``server_wide_modules = web,queue_job,integration,integration_shopify``
    | ``[queue_job]``
    | ``channels = root:1``
    | ``scheme = https``
    | ``host = <your_odoo_host> (e.g. myhost.odoo.com)``
    | ``port = 443``

   - After changing the configuration file, run ``odoosh-restart`` command in the shell.

|

Feedback
##########

- In case of any issues, please contact us at support@ventor.tech
- Don't forget to share your experience after you go live :)

  | (only person who made a purchase, can leave ratings)

|

Change Log
##########

|

* 1.9.2 (2024-01-05)
    - Refactored logic of mapping products.
    - Improved orders processing: imported orders data will be marked as "require update" to make sure that the latest updates will be downloaded during Sales Order creation in Odoo.
    - Fixed an issue with stock synchronization for products with zero stock.
    - Fixed for order cancellation: orders cancelled in external e-commerce system will be automatically cancelled if they were imported to Odoo.
    - Other small fixes and improvements.

* 1.9.1 (2023-11-22)
    - Fixed issue with import orders with empty first / last names.
    - Fixed tests (failed on Odoo.sh when MRP module isn't available).
    - Fixed issue with module upgrade (Odoo raised an exception while extracting translations due to icons in views).
    - Fixed issue with translation string when cancelling orders.
    - Other small fixes and improvements.

* 1.9.0 (2023-11-05)
    - Improved logic of states auto-mapping.
    - Improved connectors' UI/UX.
    - Improved image naming logic for products with lengthy names or with special symbols in product names.
    - Improved calculation of discount on prices with includes taxes.
    - Added support of discounts for delivery lines in Odoo.
    - Improved detection of changes in product attributes, including images, to trigger product export.
    - Added integration settings export/import wizard.
    - Fixed issue with products serialization for export to e-commerce system when 'en_US' language is inactive in Odoo.
    - Fixed export of translatable fields with empty values.
    - Fixed issue with export of images and stock during the first-time export.
    - Fixed issue with mapping product attributes / features values.
    - Other small fixes and improvements.

* 1.8.1 (2023-09-29)
    - Fixed issue with auto-workflow not executing all tasks

* 1.8.0 (2023-09-19)
    - NEW! Added ability to receive separate orders in Odoo with the newly implemented webhook “Create Order“. `(watch video) <https://www.youtube.com/watch?v=FuvXRa0ctxY>`__
    - NEW! Added the ability to exclude specific products from Stock Synchronization with the use of special checkbox in the E-commerce tab on the product form. `(watch video) <https://www.youtube.com/watch?v=l9Mu3eCPBds>`__
    - Fixed issue with update of order status to “Canceled” in Odoo.
    - Fixed issue with updating translatable fields when default ERP language different to Shopify shop language.
    - Fixed issue with missed orders.
    - Fixed issue with exporting tracking number for pickings with product kits.
    - Fixed for importing product list price for the products without variants.
    - Upgrade Shopify API to the actual version.
    - Added unit tests for testing field mapping logic within the integration module.
    - Other small improvements and fixes.

* 1.7.0 (2023-08-14)
    - NEW! Add setting for export prices via price list from Odoo to PrestaShop. Configurable based on integration. `(watch video) <https://www.youtube.com/watch?v=Q9Hh1okL3bw&ab_channel=VentorTech>`__
    - NEW! Improve automatic mapping of country states to Odoo country states.

* 1.6.1 (2023-08-03)
    - Fixed the issue for product validation during product export when finding the similar product in the API by product reference.
    - Fixed the issue related to canceling sales orders via webhook.

* 1.6.0 (2023-07-19)
    - NEW! Added the ability to synchronize product quantities from different Odoo Locations to different Shopify Locations. The configuration for this feature is available in the "Inventory" tab within the sales integration settings. `(watch video) <https://youtu.be/HT1SwSiZUmQ>`__
    - NEW! Added the option to download Shopify payments data to Sales Orders, providing information about the payment methods used for order payment. `(watch video) <https://youtu.be/q-grrBK3HTM>`__
    - NEW! Introduced a filter that allows the download of specific sales order statuses from Shopify, with the ability to filter by both financial and fulfillment statuses. `(watch video) <https://www.youtube.com/watch?v=tNmsop0-28o&ab_channel=VentorTech>`__
    - NEW! Synchronise from Shopify Fraud scores and mark order as risky in case the Fraud Score is more than specified in the configuration amount of percent. `(watch video) <https://www.youtube.com/watch?v=x7CpdqvawH0&ab_channel=VentorTech>`__
    - NEW! “Shopify Fulfilment Status“ is added as a separate field on imported Sales Orders. Also, it is updated through webhooks in case the status is changing. `(watch video) <https://www.youtube.com/watch?v=S6vA8F_54o8&ab_channel=VentorTech>`__
    - NEW! Synchronize sales order tags from Shopify to Odoo. Both on initial order download and based on webhooks. `(watch video) <https://www.youtube.com/watch?v=C0bHkT392MY&ab_channel=VentorTech>`__
    - NEW! Added the possibility to create dynamic filters for importing products from Shopify. By default, the filter is configured to import only active products. `(watch video) <https://youtu.be/__FaXxJfDe0>`__
    - NEW! Allow to download Shopify orders in the customer currency instead of the standard Shop default currency. `(watch video) <https://youtu.be/bsOprNz3ZcY>`__
    - NEW! Added setting to automatically create products on SO Import in case products doesn’t exist yet in Odoo. Configurable based on integration. `(watch video) <https://www.youtube.com/watch?v=b0aBh9XCNCI&ab_channel=VentorTech>`__
    - NEW! During initial import, the connector will generate only product variants that exist in Shopify. This behavior is configurable on the “Product Defaults“ tab on sales integration with the checkbox “Import Attributes as Dynamic“. It is switched off by default. `(watch video) <https://youtu.be/esONyR7kZ7A>`__
    - NEW! Add new behavior on empty tax “Take from the Product“. When selected, if the downloaded sales order line will not have defined taxes, it will insert on the sales order line customer tax defined on the product. `(watch video) <https://youtu.be/bShKi6TZbtc>`__
    - NEW! Allow excluding specific product attributes to synchronize from Odoo to Shopify. Can be configured in “Sales - Configuration - Attributes“. `(watch video) <https://youtu.be/LZvrutgifuU>`__
    - NEW! Discount for individual products is added as a separate line on Odoo Sales Order for proper financial records. `(watch video) <https://youtu.be/OvymmCkTsi0>`__
    - NEW! Allow switching on and off validation of missing barcodes on product variants. When “Validate missing barcodes for variants“ is enabled then the connector will validate that either all variants should have barcodes, or neither of the variants should have barcodes (the mix is not allowed). Available only in Debug mode on the “Product Defaults“ tab. `(watch video) <https://youtu.be/sL4ZOO7swpg>`__
    - In case it is configured not to download the barcode field from Shopify to Odoo (in Product Fields Mapping there is no barcode field defined) connector will not analyze external products for duplicated barcodes.
    - Synchronize taxable flag to the product in Shopify. Is set to True when there is Customer Tax, and False in the other case.
    - Download orders by batches to avoid timeout of “Receive Orders” job.
    - When exporting a new product from Odoo to Shopify that contains attributes and attribute values that were not existing in Shopify, the connector will create them automatically.
    - Mark the product as archived in Shopify when archived in Odoo.
    - Do not send inactive product variants when exporting products to Shopify.
    - Added to sales integration list of global fields that are monitored for changes. So when the product is updated and these fields are changed, then we also trigger the export of the product.
    - Product attributes are synchronized according to their sequence to preserve the same order as in Odoo.
    - Other small improvements and fixes.

* 1.5.2 (2023-04-04)
    - Fix issue with duplicated product price for products with variants on initial product import.

* 1.5.1 (2023-03-23)
    - Fix issue with impossibility to cancel sales order (in some cases) or register payment.

* 1.5.0 (2023-03-13)
    - NEW! Added “Exclude from Synchronisation” settings on the product to exclude specific products and all their variants totally from sync and all related logic (validation, auto-mapping). `(watch video) <https://youtu.be/7zO2y0Q6aS8>`__
    - NEW! Contacts that were created by the connector will have a special Tag with the name of the sales integration it was created from. That allows us to easier find all contacts created from specific integration. `(watch video) <https://youtu.be/0a0r-RDeNag>`__
    - Copy “e-Commerce payment method” from Sales Order to the related Customer Invoice.
    - Sales Orders with a non-valid EU VAT number will be created. But a warning message will be added in Internal Note for the created Sales Order informing the user about this problem.
    - Convert weight on import/export of products in case UoM in Odoo is different from UoM in Shopify (kgs vs lbs).
    - Other small fixes and improvements.

* 1.4.0 (2023-02-17)
    - NEW! Reworked product import and export mechanisms to support meta fields. Now for simple fields, no coding is required to synchronize them from/to Odoo. Fields mapping working both for initial import (Shopify -> Odoo) and for export (Odoo -> Shopify). `(watch video) <https://youtu.be/VPsw1F51aYE>`__
    - NEW! Trigger products export only if fields that are marked with the “Send field for updating“ checkbox are updated. That leads to a smaller number of export product jobs. `(watch video) <https://youtu.be/ye-z8xtqKro>`__
    - NEW! Implemented initial stock levels import functionality from Shopify to Odoo (available on the "Initial Import" tab). `(watch video) <https://youtu.be/uWsgOwI1ZdE>`__
    - NEW! Now all integration logs are available in a separate menu "Job Logs". It is possible to see everything that happened to a specific Product or Sales Order in a quick way. `(watch video) <https://youtu.be/06b1kPVFYno>`__
    - NEW! Add the possibility to define the "Orders Cut-off" date. Only orders created after this date will be synchronized. `(watch video) <https://youtu.be/AyqOlhyiFuc>`__
    - NEW! Added possibility to manage product tags from Odoo. `(watch video) <https://youtu.be/h_SvNIFwPhE>`__
    - NEW! The tracking number can now be exported even if Delivery Carrier is not mapped to Shopify Delivery Carrier. `(watch video) <https://youtu.be/84-QBQ--qlY>`__
    - Make ZIP code a non-required field for contact creation during sales order import as some countries do not require it.
    - PERFORMANCE! Overall performance improvements for the requests to Shopify.
    - Other small fixes and improvements.

* 1.3.2 (2023-01-24)
    - Fix Customer VAT (Registration) number import.

* 1.3.1 (2023-01-06)
    - Fix issue when en_US language is deactivated.
    - Add Sale Integration in product on Import Product From External.

* 1.3.0 (2022-12-28)
    - NEW! Add a setting to send products from Odoo on initial export in “inactive“ status, so products can be reviewed later and published manually. `(watch video) <https://youtu.be/NvV5wcb5qrs>`__
    - NEW! Allow defining payment terms that will be used instead of the standard on Order synchronization depending on the payment method of the sales order. `(watch video) <https://youtu.be/gDSbEe1GEGQ>`__
    - NEW! Trigger new products export only if a product has non-empty fields that are mandatory for product export. The list of fields is defined on the integration level and by default it is “Internal Reference“ only. `(watch video) <https://youtu.be/-6ruWO7qVHE>`__
    - NEW! Send the "Paid" status to Shopify after the order is fully paid in Odoo. `(watch video) <https://youtu.be/BeQRvfwt2Kw>`__
    - NEW! Added global config to allow sending tax included OR tax excluded sales price. `(watch video) <https://youtu.be/0VbrJceXibw>`__
    - NEW! Allow defining special ZERO tax that will be used in case there are no taxes defined on the imported sales order line. `(watch video) <https://youtu.be/4Pyw_HETjaM>`__
    - Export tracking number in case it is added after Picking is moved to the "Done" state (when using some third-party connectors).
    - Improve connector to allow exporting more than 10K products.
    - Added a new field on the customer to have “Company Name” as a separate field. This field is also used when displaying customer addresses on Odoo forms and on printed PDF forms (e.g. Invoices, Pickings and etc.).
    - Implement proper application of discounts from Shopify orders to Odoo orders.
    - Set the order date in Odoo to be the same as in the Shopify order. Previously it was changed by Odoo standard mechanism during order confirmation.
    - Fix auto-workflow action “Validate Picking“ not validating pickings in case of multi-step delivery.
    - “Force Export to External“ action on products is now sending products to Shopify even if automatic products export from Odoo is disabled in integration settings.
    - Added Cost Price field synchronization for initial import from Shopify to Odoo and for exporting Products from Odoo to Shopify.
    - Other small improvements and fixes.

* 1.2.8 (2022-12-18)
    - Fix for creation the shopify taxes during initial import.

* 1.2.7 (2022-12-15)
    - Fixed creation the variants of product during the initial import.

* 1.2.6 (2022-12-14)
    - Fixed creation of mappings during the initial product import.

* 1.2.5 (2022-11-25)
    - Fixed import or products when there are duplicate product attributes.

* 1.2.4 (2022-11-07)
    - Added compatibility with partner_firstname module from OCA.

* 1.2.3 (2022-10-28)
    - Fixed Feature Value creation.
    - Fixed “Import External Records“ running for Product Variants from Jobs.
    - Fixed calculation of discount in Odoo if there are several taxes in sales order.

* 1.2.2 (2022-10-19)
    - Import customers functionality was not working with all queue_job module versions.
    - Before creating a product on the Shopify side - verify if the product with such internal reference or barcode already exists. If found, just auto-map it.

* 1.2.1 (2022-10-11)
    - Improving Shopify API retry mechanism to ensure consistent data and avoid duplicated products.
    - Fix issue for product collections update flow.

* 1.2.0 (2022-10-10)
    - NEW! Allow exporting of product quantities both in real-time and by cron. Make it configurable on the “Inventory“ tab on sales integration. `(watch video) <https://youtu.be/qpNzJk2G3Lk>`__
    - NEW! Allow defining which field should be synchronized when sending the stock to the e-Commerce system. Allowing 3 options: “Free To Use Quantity“, “On Hand Quantity” and  “Forecasted Quantity”. `(watch video) <https://youtu.be/8c7yw2QT5fY>`__
    - NEW! Implemented wizard allowing to import customers based on the last update date. `(watch video) <https://youtu.be/f__ZMptKj7A>`__
    - NEW! Added setting to allow automatic creation of Delivery Carrier and Taxes in Odoo if the existing mapping is not found (during initial import and during Sales Order Import). `(watch video) <https://youtu.be/FmKa8gu4PpM>`__
    - Allow having customers without email defined.
    - Shopify has a limitation of doing not more than 2 requests per second through the same App to the same store. Implemented a retry mechanism to workaround this limitation.
    - Fix issue with auto-workflow failing in some cases when SO status is changing on webhook.
    - When an order is created with an existing partner make sure to also emulate the selection of partner on the Odoo interface so needed fields from the partner will be filled in (Payment Terms, Fiscal Positions and etc.).
    - Improved processing of the orders with empty / not defined payment method. New payment method will be created with name “Not Defined“ in this case.
    - TECHNICAL! Improve the retry mechanism for importing products and executing workflow actions to workaround concurrent update errors in some cases (e.g. sales order was not auto-confirmed and remained in draft state).
    - Do not create webhooks automatically in case integration is activated. Users need to do it manually by clicking the “Create Webhooks“ button on “Webhooks“ tab inside integration.
    - Set the proper fiscal position on automatic order import according to Fiscal Position settings.
    - Improved manual mapping of product variants and product templates in case template has only 1 variant.

* 1.1.1 (2022-09-09)
    - When exporting product from Odoo to Shopify use "Product Name" from "e-Commerce Integration" tab if defined, else use regular product name.
    - Added compatability with 2022-07 Shopify API version (requesting additional access rights 'write_merchant_managed_fulfillment_orders' and 'write_orders').
    - Usability improvements in auto-workflow configuration.
    - Improved validation procedure of the webhook from Shopify to ensure it will pass validation.
    - Sales Order date is now set equal to Order creation date from the Shopify.
    - Improve functionality for partners creation (first search partner by full address, before creating a new one).

* 1.1.0 (2022-09-02)
    - **NEW!** Major feature. Introduced auto workflow that allows based on sales order status: to validate sales order, create and validate invoice for it and register payment on created invoice. Configuration is flexible and can be done individually for every SO status. `(watch video) <https://youtu.be/0ZQugfcpm-c>`__
    - **NEW!** Added automatic creation of Webhooks to track Order Status change on the Shopify side. `(watch video) <https://youtu.be/tDkyGQUQDZ8>`__
    - During the creation of the sales order if mapping for the product was not found try to auto-map by reference OR barcode with existing Odoo Product before failing creation of sales order.
    - Send tracking numbers only when the sales order is fully shipped (all related pickings are either "done" or "canceled" and there are at least some delivered items).
    - Fix issue with product save to shopify store.
    - More verbose logging for Shopify REST.

* 1.0.0 (2022-04-01)
    - Odoo integration with Shopify.

|