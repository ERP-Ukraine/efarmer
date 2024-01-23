Integration
===========

Change Log
##########

|

* 1.15.3 (2024-01-05)
    - Refactored logic of mapping products.
    - Improved orders processing: imported orders data will be marked as "require update" to make sure that the latest updates will be downloaded during Sales Order creation in Odoo.
    - Fixed an issue with stock synchronization for products with zero stock.
    - Fixed for order cancellation: orders cancelled in external e-commerce system will be automatically cancelled if they were imported to Odoo.
    - Other small fixes and improvements.

* 1.15.2 (2023-11-22)
    - Fixed tests (failed on Odoo.sh when MRP module isn't available).
    - Fixed issue with module upgrade (Odoo raised an exception while extracting translations due to icons in views).
    - Fixed issue with translation string when cancelling orders.
    - Other small fixes and improvements.

* 1.15.1 (2023-11-08)
    - Other small fixes and improvements.

* 1.15.0 (2023-11-05)
    - Improved logic of states auto-mapping.
    - Improved connectors' UI/UX.
    - Improved image naming logic for products with lengthy names or with special symbols in product names.
    - Fixed issue with products serialization for export to e-commerce system when 'en_US' language is inactive in Odoo.
    - Fixed export of translatable fields with empty values.
    - Improved calculation of discount on prices with includes taxes.
    - Fixed issue with export of images and stock during the first-time export.
    - Improved detection of changes in product attributes, including images, to trigger product export.
    - Added integration settings export/import wizard.
    - Fixed issue with mapping product attributes / features values.
    - Added support of discounts for delivery lines in Odoo.
    - Other small fixes and improvements.

* 1.14.1 (2023-09-29)
    - Fixed issue with auto-workflow not executing all tasks

* 1.14.0 (2023-09-19)
    - NEW! Added the ability to exclude specific products from Stock Synchronization with the use of special checkbox in the E-commerce tab on the product form. `(watch video) <https://www.youtube.com/watch?v=l9Mu3eCPBds>`__
    - Fixed issue with updating translatable fields when default ERP language different to e-Commerce shop language.
    - Fixed issue with missed orders.
    - Fixed issue with exporting tracking number for pickings with product kits.
    - Added unit tests for testing field mapping logic within the integration module.
    - Other small improvements and fixes.

* 1.13.0 (2023-08-14)
    - NEW! Add setting for export prices via price list from Odoo to Magento 2. Configurable based on integration. `(watch video) <https://www.youtube.com/watch?v=Q9Hh1okL3bw&ab_channel=VentorTech>`__
    - NEW! Import prices via price list from Odoo to e-commerce system.
    - NEW! Improve automatic mapping of country states to Odoo country states.
    - Added basic automated tests for the Integration module.

* 1.12.0 (2023-07-19)
    - NEW! Allow excluding specific product attributes to synchronize from Odoo to external system. Can be configured in “Sales - Configuration - Attributes“.
    - NEW! Added setting to automatically create products on SO Import in case products doesn’t exist yet in Odoo. Configurable based on integration.
    - NEW! During initial import, the connector will generate only product variants that exist in e-Commerce Systems. For this purpose, all Attributes that are created by the connector are now created with “Creation Mode“ = Dynamic.
    - NEW! Add new behavior on empty tax “Take from the Product“. When selected, if the downloaded sales order line will not have defined taxes, it will insert on the sales order line customer tax defined on the product.
    - NEW! In case it is configured not to download the barcode field from e-Commerce System will not analyze external products for duplicated barcodes.
    - NEW! Discount for individual products is added as a separate line on Odoo Sales Order for proper financial records.
    - NEW! Allow switching on and off validation of missing barcodes on product variants. When “Validate missing barcodes for variants“ is enabled then the connector will validate that either all variants should have barcodes, or neither of the variants should have barcodes (the mix is not allowed). Available only in Debug mode on the “Product Defaults“ tab.
    - Improved logic for inventory initial import.
    - Now field with the integrations list is also tracked for changes, so changing it will trigger product export.
    - Do not send inactive product variants when exporting product to e-Commerce Systems.
    - Download orders by batches to avoid timeout of “Receive Orders” job.
    - Added to sales integration list of global fields that are monitored for changes. So when the product is updated and these fields are changed, then we also trigger the export of the product.
    - Product attributes are synchronized according to their sequence to preserve the same order as in Odoo.
    - Added basic automated tests for the Integration module.
    - Other small improvements and fixes.

* 1.11.2 (2023-04-04)
    - Fix issue with duplicated product price for products with variants on initial product import.

* 1.11.1 (2023-03-23)
    - Fix issue with impossibility to cancel sales order (in some cases) or register payment.

* 1.11.0 (2023-03-13)
    - NEW! Added “Exclude from Synchronisation” settings on the product to exclude specific products and all their variants totally from sync and all related logic (validation, auto-mapping)
    - NEW! Contacts that were created by the connector will have a special Tag with the name of the sales integration it was created from. That allows us to easier find all contacts created from specific integration
    - Copy “e-Commerce payment method” from Sales Order to the related Customer Invoice
    - Sales Orders with a non-valid EU VAT number will be created. But a warning message will be added in Internal Note for the created Sales Order informing the user about this problem
    - Convert weight on import/export of products in case UoM in Odoo is different from UoM in e-Commerce System (kgs vs lbs).
    - Other small fixes and improvements.

* 1.10.0 (2023-02-17)
    - NEW! Reworked product import and export mechanism to allow flexible configuration of product fields that are downloaded from external system to Odoo and that are exported from Odoo to external system.
    - NEW! Trigger products export only if fields that are marked with “Send field for updating“ are updated.
    - NEW! Now it is possible to see everything that happened to a specific Product or Sales Order in a quick way in the Jobs menu or by navigating from a specific Product or Sales Order.
    - NEW! Define the date and time from which you need to synchronize orders.
    - Improved performance of requests to e-commerce system.
    - Moved Export of images and inventory to a separate jobs to easily debug issues with it.
    - Make ZIP code non-required field for contacts during sales order creation as some countries do not require it.
    - Other small improvements and fixes.

* 1.9.2 (2023-01-24)
    - Fix Customer VAT (Registration) number import.

* 1.9.1 (2023-01-06)
    - Fix issue when en_US language is deactivated.
    - Add Sale Integration in product on Import Product From External.

* 1.9.0 (2022-12-28)
    - NEW! Add a setting to send products from Odoo on initial export in “inactive“ status, so they can be reviewed and published manually.
    - NEW! Mark Sales Order as Paid on e-Commerce System in case all related invoices are Paid.
    - NEW! Allow defining payment terms that will be used instead of the standard.
    - NEW! Trigger new products export only if product has non-empty fields mandatory for a product export.
    - NEW! Send "Paid" status to external system either after all invoices are validated or all invoices are marked as paid (depending on "Send payment status when" property on the payment method).
    - NEW! Added global config to allow sending tax included sales price.
    - NEW! Allow defining special ZERO tax that will be used in case there are no taxes defined on the imported sales order line.
    - Improve connector to allow exporting more then 10K products.
    - Added new field on the customer to have Company Name. This field is also used when displaying customer address on Odoo and on printed forms.
    - Fix for applying discounts from Shopify.
    - Fix for performing automatic workflow tasks manually in a standard way.
    - Now order date is the same in external system and in Odoo. Taking into account sales order time zone.
    - Added controller to allow retrieving PDF Invoices from Odoo with API Key by external system Order ID.
    - Fix auto-workflow action “Validate Picking“ not validating pickings in case of multi-step delivery.
    - Force sending products to the external e-Commerce system is now working also if automatic products export from Odoo is disabled.
    - Fixed known vulnerabilities in handling webhooks.
    - More verbose webhooks logging.
    - Improved performing "receive orders" function (including webhooks).
    - Export tracking number in case it is added after Picking is moved to "Done" state.

* 1.8.6 (2022-12-16)
    - Fixed bug when importing with value assignment in different languages.

* 1.8.5 (2022-12-14)
    - Fixed creation of mappings during the initial product import.

* 1.8.4 (2022-11-25)
    - Fixed import or products when there are duplicate product attributes.

* 1.8.3 (2022-11-07)
    - Added compatibility with partner_firstname module from OCA.
    - Fixed import of gift line.

* 1.8.2 (2022-10-28)
    - Fixed Feature Value creation.
    - Fixed “Import External Records“ running for Product Variants from Jobs.
    - Fixed calculation of discount in Odoo if there are several taxes in sales order.

* 1.8.1 (2022-10-18)
    - Import customers functionality was not working with all queue_job module versions.

* 1.8.0 (2022-10-10)
    - NEW! Allow exporting of product quantities both in real-time and by cron. Make it configurable on the “Inventory“ tab on sales integration.
    - NEW! Allow defining which field should be synchronized when sending the stock to the e-Commerce system. Allowing 3 options: “Free To Use Quantity“, “On Hand Quantity” and  “Forecasted Quantity”.
    - NEW! Implemented wizard allowing to import customers based on the last update date.
    - NEW! Implementing Gift Wrap synchronization from Prestashop to Odoo as a separate line in sales orders.
    - NEW! Added setting to allow automatic creation of Delivery Carrier and Taxes in Odoo if the existing mapping is not found (during initial import and during Sales Order Import).
    - NEW! Implemented discount handling for Magento 2 "Cart Rules" to be porperly synchronized into Odoo (coupon code will be added to description of the product line).
    - Make email non-required (as Shopify can have either email or phone).
    - When guessing the partner search by email if it exists, if no email try to add Phone to search criteria.
    - Fix issue with auto-workflow failing in some cases when SO status is changing on webhook.
    - When an order is created with an existing partner make sure to also emulate the selection of partner on the Odoo interface so needed fields from the partner will be filled in (Payment Terms, Fiscal Positions and etc.).
    - TECHNICAL! Improve the retry mechanism for importing products and executing workflow actions to workaround concurrent update errors in some cases (e.g. sales order was not auto-confirmed and remained in draft state).
    - Do not create webhooks automatically in case integration is activated. Users need to do it manually by clicking the “Create Webhooks“ button on “Webhooks“ tab inside integration.
    - Set the proper fiscal position on automatic order import according to Fiscal Position settings.
    - Improved manual mapping of product variants and product templates in case template has only 1 variant.

* 1.7.1 (2022-09-08)
    - Added possibility to specify additional field where Sales Order reference from external e-Commerce system will be added (for example "Client Reference" field on SO).
    - "Product Defaults" tab on integration now visible for all integrations.
    - Improve functionality for partners creation to adapt it to Shopify needs.

* 1.7.0 (2022-09-05)
    - NEW! Major feature. Introduced auto workflow that allows based on sales order status: to validate sales order, create and validate invoice for it and register payment on created invoice. Configuration is flexible and can be done individually for every SO status.
    - NEW! Added logic to allow creating webhooks on e-Commerce system for automatic tracking of the order status changes.
    - Implemented separate functionality of products mapping (trying to map with existing Odoo Product) from products import (trying to map and if not found create product in Odoo).
    - Add possibility to call "Try Map Products" from External -> Products and External -> Mappings menus.
    - During creation of sales order if mapping for product was not found trying to auto-map by reference OR barcode with existing Odoo Product before failing creation of sales order.
    - Send tracking numbers only when sales order is fully shipped (all related pickings are either "done" or "cancelled" and there are at least some delivered items).
    - Made improvements for connector to support 50 000 Products.
    - Fixing issue with synchronizing records with special symbols in their name ("%", "_" , etc.).
    - Allow to disable export of product images from Odoo to e-Commerce Systems.

* 1.6.0 (2022-07-21)
    - Added possibility to define Cancel action for the integration.
    - Added Product Features / Product Feature values related models (to be used in specific connectors).
    - Added possibility to define “Default Sales Person” on sales integration. So it will be automatically set when new received SO is created.
    - Saving external e-commerce system sales order reference to separate field “External Sales Order Ref“ on Sales Order.
    - Allow to select only Sales Taxes in “Mappings - Taxes” menu.
    - Try automatically map products not only by internal reference, but also by barcode (if it exists).
    - Added the ability to work both with the Manufacturing module and without it.
    - Added the ability to work both with the eCommerce module and without it.
    - Not Allow to define for 2 integrations same “Sales order prefix“.
    - If sales order prefix is used, don't generate standard SOXXX and use PREFIX/Order_name instead.
    - Added hierarchy to External Categories view for easier navigation.
    - TECHNICAL: Added possibility to easily extend module for adding custom fields.

* 1.5.5 (2022-06-16)
    - Fixed incorrect name of constraint for internal records.
    - Automatically cleanup non-existing external product and product variants records (in case not found in external system).
    - Do not fail job in case images or inventory where not exported properly during Export Template job. That helps to avoid duplicates in external system.
    - Before exporting products from Odoo to external system double check that same product already exists in external e-Commerce system. If exists then map it automatically by internal reference.

* 1.5.4 (2022-06-12)
    - Group taxes and tax groups together according to the integration.
    - Link external product variants and product templates.
    - Link external product attributes to corresponding external attribute values.
    - When exporting product from Odoo to Prestashop make sure to export also External Reference.
    - Added functionality to auto-create missing integration settings (so we have flexibility to add them without migrations).

* 1.5.3 (2022-06-09)
    - Give ability define allowed sales integrations separately for every product variant.
    - Add quick filters for product variants/templates list to be able to quickly find which product belongs to which integration.
    - Add mass action on product variants/templates to change integration product is attached to.
    - Allow to define if product should be automatically attached to the specific integration on its creation with special checkbox on sales integration object.
    - Add to the integration possibility to associate all mapped products with this integration (in action "Link All Mapped Products").

* 1.5.2 (2022-06-02)
    - Added possibility to import payment transactions.
    - When creating taxes from integration, set link to the specific integration from Odoo Tax (to know from which integration tax was created).

* 1.5.1 (2022-05-16)
    - Solve issue with multi-company setup and automatic sales order download.
    - Set proper currency on Sales Order if it is different from company standard.
    - Multi-step delivery: Send tracking number ONLY for outgoing picking.

* 1.5.0 (2022-05-01)
    - Added Quick Configuration Wizard.
    - Added taxes and tax groups quick manual import.
    - Version of prestapyt library changed to 0.10.1
    - Fixed initial payment methods import.
    - Fixed import BOMs with no product variant components.
    - Fixed incorrect tax rate applied to order shipping line.
    - When importing sales order, payment method is also created if it doesn't exist.
    - When integration is deleted, also delete related Sales Order download Scheduled Action.

* 1.4.4 (2022-04-20)
    - Added filter by active countries and states in initial import.
    - Fixed order import when line has several taxes.
    - Fixed product import.

* 1.4.3 (2022-03-31)
    - Added import of payment method before creating an order if it does not exists.
    - Added integration info in Queue Job for errors with mapping.
    - Added possibility to import product categories by action “Import Categories“ in menus “External → Categories“ and “Mappings → Categories“.
    - Added button "Import Product" on unmapped products in menu “Mapping → Products“.
    - Fixed issue with export new products.
    - Fixed product and product variant mapping in initial import.
    - Fixed empty external names after export products and import orders.

* 1.4.2 (2022-03-11)
    - Sale order line description for discount and price difference is assigned from product.

* 1.4.1 (2022-03-01)
    - Fix issue with difference per cent of the total order amount.

* 1.4.0 (2022-02-17)
    - Added possibility to import product attributes and values by action “Import Products Attributes“ in menus “External → Product Attributes“ and “Mappings → Product Attributes“.
    - Added creation of Order Discount from e-Commerce System as a separate product line in a sell order.
    - Fix issue with trying to send stock to e-Commerce for products that has disabled integration.
    - Fix bug of mapping modification for users without role Job Queue Manager.

* 1.3.5 (2021-12-31)
    - Added button "Import Stock Levels" to “Initial Import“ tab that tries to download stock levels for storable products.
    - Fixed bug of delivery line tax calculation.

* 1.3.4 (2021-12-24)
    - Added “Initial Import“ tab with two separate buttons into “Sale Integration“:
        - “Import Master Data“ - download and try to map common data.
        - “Import products“ - try to import products from e-Commerce System to Odoo (with pre-validation step).
    - Added possibility to import products by action Import Products in menu “External → Products“.
    - Import of products is run in jobs separately for each product.

* 1.3.3 (2021-11-22)
    - Downloaded sales order now is moved from file to JSON format and can be edited/viewed in menu “e-Commerce Integration → Sales Raw Data“.

* 1.3.2 (2021-10-27)
    - Synchronize tracking only after it is added to the stock picking. Some carrier connectors.

* 1.3.1 (2021-10-18)
    - Added synchronization of partner language and partner email (to delivery and shipping address).

* 1.3 (2021-10-02)
    - Automapping of the Countries, Country States, Languages, Payment Methods.
    - Added Default Sales Team to Sales Order created via e-Commerce Integration.
    - Added synchronization of VAT and Personal Identification Number field.
    - In case purchase is done form the company, create Company and Contact inside Odoo.

* 1.2 (2021-09-20)
    - Added possibility to define field mappings and specify if field should be updatable or not.
    - Avoid creation of duplicated products under some conditions.

* 1.1 (2021-06-28)
    - Add field for Delivery Notes on Sales Order.
    - Added configuration to define on Sales Integration which fields should be used on SO and Delivery Order for Delivery Notes.
    - Allow to specify which product should be exported to which channel.
    - If e-Commerce Product Name is not empty, send it instead of standard Product Name.

* 1.0.5 (2021-06-25)
    - Fixed a bug of creating duplicate sale orders.

* 1.0.4 (2021-06-01)
    - FIX: Prestashop should send name of the product, not display_name.

* 1.0.3 (2021-05-28)
    - Fixed warnings on Odoo.sh with empty description on new models.

* 1.0.2 (2021-04-21)
    - Added statistics widget
    - Create missing mappings on receiving of orders.
    - Requeue needed jobs when mappings are fixed.

* 1.0.1 (2021-04-13)
    - Added Check Connection.

* 1.0 (2021-03-23)
    - Initial implementation.

|