Shopify Integration
===================

Feedback
########

- In case of any issues, please contact us at support@ventor.tech
- Don't forget to share your experience after you go live :)

  | (only person who made a purchase, can leave ratings)

|

Change Log
##########

|

* 2.2.0 (2026-08-07)
    - [BREAKING] Order status export behavior change: the Cancelled / Paid / Shipped status exports now work on their own, without the former master "status export" toggle. A store that had one of them enabled while the master option was disabled will start sending that status after the upgrade — review each store's Automation Jobs settings after updating.
    - [NEW] Added support for import duties in Shopify orders (e.g. Shopify Managed Markets). Duties charged on an order line are now imported as a separate "Duties for <product>" line on the Sales Order, with their taxes, instead of being lost. A new "Duties Product" setting on the Sales Orders tab defines the service product used for these lines — if an order contains duties while the setting is empty, the import stops with a message explaining what to configure.
    - [NEW] Added a "Default Invoice Date" setting to the Auto-Workflow configuration (per e-commerce order status, next to "Create Invoice"), letting you choose whether invoices created by the connector use the Sales Order date ("Order Date", default — previous behavior) or the date the invoice is actually created.
    - [NEW] Added a "Consistency Wizard" on the Data Import tab (available in debug mode) to detect discrepancies between the external records stored in Odoo and the actual data in the e-commerce store. For the selected entity — products, attributes, categories, taxes, shipping and payment methods, and more — it reports which records no longer exist in the store, which are not mapped to an Odoo record, and, for products, which have a variant mismatch. Obsolete external records can be deleted right from the wizard.
    - [NEW] Added a "Refresh Stock from Store" action on the product form, allowing users to pull current stock levels from an e-commerce store for a single product on demand. The wizard asks which store to read from and which Odoo location to apply the quantities to, then applies them to the product's variants via an inventory adjustment. This replaces existing quantities in the mapped locations, so it is intended for controlled stock alignment rather than routine synchronization.
    - [NEW] Added a "Payment Method" field on external payment methods, next to "Payment Journal", allowing e-commerce payment methods to be mapped to Odoo payment methods. It is applied to all payments created by the connector; when left empty, the journal's default is used.
    - [NEW] Added detailed order import trace logs, showing which pages were fetched, how many orders each contained, and how the import resume date moved. To enable, activate the "Save Logs" checkbox on the Testing tab and add "Orders Import" to the Log Types.
    - [IMP] Reworked product → store synchronization to clearly separate linking a product from publishing it. Selecting a store on a product no longer immediately publishes or overwrites its content and images in the store. Publishing is now always an explicit action: the new "Export to Stores" button on the product, or "Link & export now" in the redesigned "Manage Store Connections" mass action, which offers per-store choices (Link only / Link & export now / Unlink) and a confirmation step before anything is sent — preventing accidental overwrites of live listings. "Auto-Export Product Updates" now does only what its name implies: it keeps already-published products up to date and never performs the first publish.
    - [IMP] Reworked "Auto-Export New Products" (per store). When enabled, newly created products are automatically linked to the store and published — but only once they satisfy that store's "Required Fields for Initial Export" (e.g. internal reference / SKU), so incomplete products are never sent. Until a product is ready it is shown as pending first export, with a banner listing what is still missing. Existing connections keep their previous setting on upgrade.
    - [IMP] Unified order fulfillment and status export so each event works on its own. "Auto-Export Shipments & Tracking" now marks orders as shipped/fulfilled in the store on all platforms when a delivery is validated in Odoo (the tracking number is optional), and the Cancelled, Paid/Invoiced and Shipped status exports each push on their own dedicated option, while "Auto-Export Manual Status Changes" now covers only status changes made by hand on an order. The Automation Jobs tab was reorganized to match: clearer option names, each setting grouped with its related option, lighter inline help, and a quick link to configure when the paid status is sent per payment method.
    - [IMP] Redesigned the auto-workflow ("Order Automation") form around a clear summary of what happened: the current state of every step, which step the automation stopped at, and the error itself shown directly on the form. A failed step no longer produces a separate failing background job with an unexplained error message — instead, the step can be retried or, when it is safe to do so, skipped right from the form, so most failures can be resolved without contacting support.
    - [IMP] Reworked the per-order-status automation configuration. The order statuses list now shows a "Will Do" column summarizing what each status triggers (individual step checkboxes are hidden by default), and the status form previews the effective sequence of steps that will actually run, taking dependencies between them into account — so it is clear upfront that, for example, enabling payment registration also requires an invoice. A new bulk wizard allows configuring the same automation steps for several order statuses at once.
    - [IMP] Cleaned up the external order form and list. A new "Automation Status" field (Done / Running / Failed / Skipped / Cancelled) replaces the previous unreliable error indicator and is shown as a colored column in the list, making it easy to spot orders whose automation needs attention. The unexplained pipeline buttons were removed from the form — automation is now managed from the "Order Automation" form itself — and the remaining fields were regrouped for readability.
    - [IMP] Improved the product catalog validation test ("Run Validation Test"). Validation now runs through the import wizard and offers a new "Run Validation in Background" option that fetches the catalog in batches via background jobs — preventing request timeouts when validating large or slow stores.
    - [IMP] Product export validation now lists all missing required fields at once, each with both its user-friendly label and technical name (e.g. "Internal Reference" (default_code)), making products easier to fix before export.
    - [IMP] Added the ability to delete a single webhook directly from the Webhooks list, instead of only removing all of them at once. The webhook is deleted both in Odoo and in the e-commerce store after confirmation; if the store's API rejects the request, the webhook is kept in Odoo and the error is shown to the user.
    - [IMP] Multiple small UI/UX improvements across connector views, including in-context guidance on the product and store-connection screens explaining what each action does.
    - [FIX] Fixed an issue where taxes were dropped from order lines and shipping lines with a zero taxable amount — a free shipping line, a fully discounted product, or a 100%-off promotion — leaving the imported Sales Order line without any tax. Tax lines are now validated against the actual taxable base after discounts, so only genuinely inconsistent ones are skipped.
    - [FIX] Fixed a critical issue where orders could be skipped or missed when a single import run had to fetch more than one page of orders (typically 250+ orders — after a long connector downtime, an initial import, or a bulk update in the store).
    - [FIX] Fixed an issue where order import failed when an order line referenced a product variant that could not be found in Odoo. The configured "Fallback Product" is now applied in this case as well, instead of only for lines with missing SKU or ID details.
    - [FIX] Fixed a misleading result message for the "Auto-Link" action on product mappings, which reported a successful import even when no Odoo product was actually linked. The action now returns a proper Auto-Link summary and can be run on several selected products at once.
    - [FIX] Fixed an issue where duplicating a product field definition via Odoo's standard "Duplicate" action created a broken, non-editable record. It now produces the same editable copy as the "Duplicate to Edit" button.
    - [FIX] Fixed an issue where webhooks stopped working on databases named "odoo". Since Odoo 18.0 the standard web client is served from /odoo, which conflicted with the connector's webhook URLs. Webhook endpoints have been moved to a dedicated path that cannot clash with Odoo's own routes; previously registered webhooks keep working, so no reconfiguration is needed.
    - [FIX] Other improvements and fixes implemented to boost overall performance, stability, and reliability. 

* 2.1.6 (2026-06-23)
    - [IMP] Custom Shopify product metafields can now be configured directly in field definitions. The "Metafield" toggle is now editable and no longer requires a special metafields. prefix — enter the API field name exactly as shown in Shopify (e.g. custom.my_field). Metafield values are always serialized as text, with numbers and true/false converted automatically; structured types (lists, money, dimensions, JSON) can be handled with a Data Transformation script.
    - [IMP] Added support for synchronizing the Shopify product "Vendor" field. The vendor is now retrieved when importing products from Shopify and is available for field mapping.
    - [IMP] Extended Shopify GraphQL API idempotency support to the inventory item activation mutation, completing compatibility with Shopify's latest API requirements and further preventing duplicate inventory changes when requests are retried under poor network conditions.
    - [IMP] Added a "Store Mappings" smart button on product field definitions, showing how many store-specific mappings use the definition and opening them in one click.
    - [IMP] Aligned the column order in mapping lists so the external (e-commerce) record is always shown before the Odoo record, matching the rest of the mapping views (Category Mappings).
    - [FIX] Fixed a critical issue where orders could be silently skipped during import and never appear in Odoo. Order sync paged results by one date field while sorting by another, so on stores that frequently update older orders (e.g. subscriptions, reships) recent orders could be permanently missed once a sync window exceeded one page. Orders are now paged and sorted consistently, ensuring none are skipped.
    - [FIX] Fixed an issue where the shipping cost was dropped from imported marketplace orders (e.g. Amazon via Shopify Marketplace Connect), leaving the Odoo order total short by the shipping amount. For these orders Shopify provides the carrier on the order's shipping line rather than the fulfillment delivery method; the shipping line is now used as a fallback. These marketplace shipping methods are also surfaced during "Import Master Data" so they can be mapped to Odoo carriers manually.
    - [FIX] Fixed an issue where product metafield translations were not imported from Shopify and could cause the translation import to fail.
    - [FIX] Fixed metafield value clearing in both directions: emptying a metafield value in Odoo now removes the metafield in Shopify (Shopify ignores empty values on update, so the metafield is now deleted), and clearing a metafield in Shopify now clears the mapped field in Odoo instead of keeping the old value.
    - [FIX] Fixed product metafield value serialization for numeric and boolean types, which previously caused export errors or lost values (e.g. a decimal 0.0 being rejected by Shopify or sent as an empty value).
    - [FIX] Improved contact matching during order import to prevent duplicate contacts. A previously mapped contact that has no parent company is no longer reused when the order requires a company (B2B) context, and company assignment changes are now detected correctly — avoiding wrongly reused or duplicated contacts.
    - [FIX] Fixed an issue where e-commerce payments registered in a currency different from the order currency were recorded without conversion, resulting in an incorrect payment amount. The amount is now correctly converted from the external currency into the order currency.
    - [FIX] Fixed an issue where matching existing Odoo records by name during import used the current user's language instead of the integration's store language. In multi-language setups this could fail to find existing records (attributes, categories, delivery carriers, taxes, pricelists, order sub-statuses) and create duplicates. Matching now consistently uses the integration language.
    - [FIX] Fixed an issue where a block-level export job could be linked to the wrong record — a product template ID was stored in the field meant for the e-commerce store — causing the job to reference an incorrect record.
    - [FIX] Other improvements and fixes implemented to boost overall performance, stability, and reliability.

* 2.1.4 (2026-05-27)
    - [NEW] Added a new product field mapping for Sales Channels, allowing users to manage which Shopify sales channels each product is published to. When enabled, sales channel assignments are synchronized in both directions — import from Shopify to Odoo and export from Odoo to Shopify.
    - [IMP] Updated Shopify GraphQL API inventory and refund mutations to comply with Shopify's API 2026-04 requirements. The connector now supports idempotency directives for inventory and refund operations, preventing duplicate inventory changes and double refunds when retrying failed requests under poor network conditions.
    - [IMP] The Shopify Carrier Code field is now available directly in the delivery carrier mapping table, making it easier to configure during the initial setup. The field has also been converted to a dropdown selection, allowing users to choose from predefined values instead of entering them manually — reducing configuration errors and improving discoverability.
    - [IMP] Added "Auto-Link" button for attribute values, allowing users to quickly map external attribute values to existing Odoo attribute values — particularly useful when working with custom attribute mappings.
    - [IMP] Improved VIES VAT validation handling when the service is temporarily unavailable or overloaded. The connector now automatically retries the request up to 3 times before proceeding — and if the service remains unavailable, the order is imported successfully with a note added to the contact's chatter to flag the unvalidated VAT number.
    - [FIX] Fixed an issue where product variant import was limited to 250 variants per product. The connector now correctly handles pagination and imports all variants regardless of the total count.
    - [FIX] Fixed an issue where product export used incorrect company context in multi-company setups. When a product was shared between multiple companies, the connector could export data (such as taxes and cost price) from the wrong company instead of the one associated with the integration, resulting in incorrect values being sent to the e-commerce store.
    - [FIX] Fixed an issue where external records created during product export were assigned the name "False" instead of the actual product name from the e-commerce store. This occurred when the connector detected an existing matching product and switched to import mode — the product name is now correctly retrieved and stored on the external record.
    - [FIX] Fixed an issue where product webhooks did not respect the product import filters configured in the integration settings (e.g. "import active products only"). Products received via webhooks are now validated against the same filters as the regular import process, preventing unwanted products from being created in Odoo.
    - [FIX] Fixed an issue where product export failed with a "Duplicate internal reference" error in multi-company setups when two companies had products with the same SKU. The connector now correctly scopes the duplicate SKU check to the integration's company, allowing products with identical SKUs across different companies to be exported without conflict.
    - [FIX] Other improvements and fixes implemented to boost overall performance, stability, and reliability.

* 2.1.3 (2026-04-08)
    - [NEW] Added support for Shopify Standard Product Taxonomy Categories synchronization. Taxonomy categories are automatically imported from Shopify during the initial master data import. A new "Shopify Product Category" field is available on the product template, allowing users to classify products according to Shopify's standard taxonomy. Category import is enabled by default; export is disabled by default to prevent accidental overwrites.
    - [IMP] Product tag synchronization is now disabled by default for both import and export. Users who rely on tag synchronization will need to enable it manually in the integration settings.
    - [IMP] The Transaction Date imported from the e-commerce store is now used as the Payment Date when creating payments in Odoo, ensuring payment records accurately reflect the original transaction date rather than the date of import.
    - [IMP] The "Allow Multi-Company Inventory Calculation" setting has been removed. Multi-company stock calculation per location is now always enabled automatically with the correct company context applied, simplifying configuration.
    - [IMP] API credentials (access tokens, secret keys, passwords) are now masked in connector authentication wizards, preventing sensitive information from being accidentally exposed.
    - [IMP] When using the "Auto-Link" button on a product mapping, the result is now displayed in a dialog instead of silently failing or showing a raw error message.
    - [IMP] Multiple small UI/UX improvements across connector views to enhance usability and overall user experience.
    - [FIX] Fixed an issue where product variants remained archived in Odoo after the product was unarchived via webhook, causing the product to appear active while its variants were still inactive.
    - [FIX] Fixed an issue where inventory export in multi-company setups could ignore configured stock locations belonging to a different company than the one set on the store connection, causing incorrect stock quantities to be sent to the e-commerce store.
    - [FIX] Fixed a critical issue where preprocessing scripts in "Order and Delivery Attribute Import Mapping" silently failed on Odoo 19.0, returning empty values instead of the computed result. The failure was caused by an incompatible argument in the script execution engine and was not visible to the user — only a hidden warning log was generated. All attribute import mappings that use preprocessing scripts are now working correctly.
    - [FIX] Fixed an issue where custom field mappings were incorrectly marked as system fields after migrating from version 1.X.X to 2.X.X.
    - [FIX] Fixed an issue where webhooks were incorrectly rejected after a store URL migration. The connector now validates webhooks against both the primary URL and the original URL stored in the integration settings, ensuring uninterrupted webhook processing during and after URL changes.
    - [FIX] Fixed an issue where "Pick and Collect" shipping methods were always imported with the same name regardless of the selected pickup location, making it impossible to distinguish between different pickup points on imported Sales Orders.
    - [FIX] Other improvements and fixes implemented to boost overall performance, stability, and reliability.

* 2.1.2 (2026-03-20)
    - [NEW] Added detailed contact handling trace logs during order import to help diagnose how customers, delivery addresses, and invoice addresses are resolved. To enable, activate the "Save Logs" checkbox on the Testing tab and add "Customers Sync" to the Log Types. A "View Contact Trace" button on the external order form provides quick access to the saved trace for each imported order.
    - [NEW] Added support for "Create Advance Payments (Before Invoice)" — a new option in the Sales Orders tab (requires "Auto-Apply Payments from E-Commerce System" to be enabled). When active, the connector registers payments directly on the Sales Order at import time, before any invoice is created, using the OCA sale_advance_payment module. The auto-workflow payment step is fully compatible — it will skip payment creation if the advance payment already covers the invoice, or register only the remaining balance if partially covered.
    - [NEW] Added support for filtering orders by Shopify Business Entity (merchantBusinessEntity). Users can now create separate Odoo integrations for each company, all pointing to the same Shopify store, with each integration filtering orders by the relevant business entity. This ensures orders are automatically routed to the correct Odoo company, including correct invoice assignment.
    - [IMP] Added partial Spanish language translation for the connector interface (65% complete). We welcome community contributions to help translate the connector into other languages - if you'd like to help, please reach out to us at support@ventor.tech.
    - [IMP] Improved Shopify Risk UI on the Sales Order. The risk level is now displayed prominently as a warning directly on the order form, and a new "View Risk Details" button on the E-Commerce Integration tab provides quick access to the full risk assessment, making it easier to identify and act on potentially fraudulent orders.
    - [FIX] Fixed an issue where customer matching during order import incorrectly fell back to name-based search when the configured search fields (e.g. email) had no value in the incoming order. This could cause orders without an email address to be incorrectly linked to an existing contact with the same name, leading to wrong order assignments and data privacy issues. The connector now respects the configured search fields strictly and creates a new contact instead of falling back to default matching criteria.
    - [FIX] Fixed an issue where real-time inventory synchronization was not triggered after completing a manufacturing order when "Forecasted Quantity" was selected as the Inventory Quantity Source Field, causing the produced product's stock level to remain outdated in the e-commerce store.
    - [FIX] Fixed a critical issue where orders could be silently missed during synchronization due to date filters being sent to the Shopify GraphQL API in incorrect format. Shopify interpreted the dates in the store's local timezone instead of UTC, causing orders to be excluded from sync results. This particularly affected stores in timezones significantly different from UTC (Americas, Asia-Pacific). Date filters are now correctly formatted using ISO 8601 with an explicit UTC indicator.
    - [FIX] Fixed an issue where Shopify order risk data was not correctly imported to Odoo, ensuring fraud risk information is accurately reflected on the Sales Order.
    - [FIX] Fixed an issue where product tags were not imported during the initial import of master data from the e-commerce store to Odoo.
    - [FIX] Other improvements and fixes implemented to boost overall performance, stability, and reliability.

* 2.1.1 (2026-03-01)
    - [NEW] Added "Export Inventory Now" button to the Inventory tab, allowing users to manually trigger a full inventory export for all products at any time — regardless of the Scheduled Inventory Sync setting. The export runs in batches as background jobs, the same way the scheduled action does.
    - [NEW] Added "Run Now" button on background jobs (available in debug mode), allowing jobs to be executed in real time instead of being queued. This is primarily intended to simplify debugging and issue investigation.
    - [NEW] Added support for importing "Additional Details" from Shopify orders, allowing users to extract and map VAT number and Personal ID fields using two new configuration options: "Additional Details Key for VAT Number" and "Additional Details Key for Personal ID". Additional details data is also now available in the "Order and Delivery Attribute Import Mapping" feature, enabling users to save any additional details values to custom fields on Sales Orders or Deliveries.
    - [IMP] Added pre-defined filters "Mapped to Store(s)" and "Not Mapped to any Store" on the product list, making it easier to identify which products are synchronized with your e-commerce store and which still require mapping.
    - [IMP] Improved shipping discount handling during order import. The connector now correctly creates discount lines for shipping coupons by fetching the original pre-discount shipping price from Shopify and computing discount allocations the same way it does for product lines. When "Add Multiple Discount Lines" is enabled, shipping discount lines include the coupon code in the description and are placed immediately after the delivery line.
    - [FIX] Fixed an issue where external records for newly created categories did not have the parent category set, causing inconsistency with imported categories where the parent was correctly assigned.
    - [FIX] Fixed an issue where zero-amount tax lines returned by the Shopify API (where the rate is non-zero but the amount is zero) were incorrectly applied in Odoo, causing the order total in Odoo to be higher than in Shopify. Such tax lines are now detected and skipped during order import.
    - [FIX] Fixed an error during order import that occurred when a Shopify order had neither a billing nor a shipping address, causing an "Address with id= not found" error. Such orders are now handled gracefully.
    - [FIX] Other improvements and fixes implemented to boost overall performance, stability, and reliability.

* 2.1.0 (2026-02-18)
    - [NEW] Added support for managing “Track quantity" and “Continue selling when out of stock" settings from Odoo. Two new checkboxes are now available on the product template, allowing users to control Shopify inventory tracking behavior directly from Odoo.
    - [NEW] Added support for synchronizing “Country of Origin" and “HS Code" with Shopify. These product fields can now be managed directly from Odoo and synchronized to Shopify.
    - [IMP] Enhanced UI/UX across connector views, based on customer feedback. The Status menu is now more functional, with quick access to unmapped records, store connections, and other key areas. The connections Kanban view was also improved, including a small 7-day orders chart and overall usability refinements to make daily monitoring and navigation more efficient.
    - [IMP] Improved initial product import batching logic. When importing products in batches, the connector now processes all valid products even if some items contain errors (e.g., missing or duplicated SKU). Problematic products are automatically grouped into a separate background job with a clear error message, allowing users to fix issues and requeue only the affected records - without blocking the entire batch.
    - [IMP] Improved multi-company product synchronization logic. The connector now validates the company on products during synchronization, ensuring that only products belonging to the integration’s company (or with no company set) are used. A new “Apply Company on Product" option was also added (disabled by default). When enabled, newly created products will automatically inherit the connection’s company, helping maintain clean and consistent multi-company data separation.
    - [FIX] Resolved an issue in the auto-workflow picking validation that could cause an infinite loop when button_validate() returned a wizard instead of completing the transfer. The connector now correctly stops auto-validation in such cases, preventing repeated background job execution while preserving normal validation behavior.
    - [FIX] Improved contact handling during order import. If a previously mapped Odoo contact is archived, the connector now ignores the existing mapping and creates a new active contact instead of assigning the archived one to the Sales Order.
    - [FIX] Improved translation handling on imported Sales Orders. Order lines now consistently use the customer’s language (not the Odoo UI language), including product names and discount line descriptions (e.g., "Discount for ..."). The connector also includes safe fallbacks when customer language or translations are missing.
    - [FIX] Resolved an issue with catalog synchronization that could trigger the error “The limit for simultaneous publication updates has been exceeded." The connector now handles publication updates more safely, preventing API limit conflicts during catalog synchronization.
    - [FIX] Resolved a GraphQL product export error related to option handling (CANNOT_DELETE_OPTION_WITH_MULTIPLE_VALUES). The connector now properly manages Shopify product options during export, preventing failures when updating products with multiple option values.
    - [FIX] Fixed an issue where “Compare At" prices were not exported correctly from the designated pricelist. The connector now properly synchronizes values from the configured “Sale Pricelist for Product Export" to Shopify, ensuring accurate sale and reference pricing.
    - [FIX] Other improvements and fixes implemented to boost overall performance, stability, and reliability.

* 2.0.0 (2026-01-23)
    - [BREAKING] This is a major release with backward-incompatible changes. Please review the `release notes <https://ecosystem.ventor.tech/faq/release-notes/>`__ before upgrading.
    - [NEW] Migrated Shopify connector to the GraphQL API. The connector now uses Shopify’s modern GraphQL API instead of the deprecated REST API, delivering improved performance, better stability, and long-term compatibility with Shopify’s platform.
    - [NEW] Added support for Shopify Markets & Catalogs synchronization. The connector now allows mapping Odoo pricelists to Shopify catalogs, enabling accurate and flexible price synchronization across multiple Shopify markets directly from Odoo. This makes it easier to manage region-specific pricing from a single system.
    - [IMP] Updated Shopify app authentication to support the new Shopify Dev Dashboard and OAuth flow.
    - [IMP] Product field mapping engine fully refactored. The connector now supports flexible and extensible product field mappings, including custom Python-based transformation logic configurable directly from the Odoo UI.
    - [IMP] Refactored product and order tag synchronization. The Shopify connector now uses a dedicated tags field instead of the previous Feature-based workaround.
    - [IMP] Optimized Shopify synchronization performance. The connector now avoids unnecessary additional API requests during synchronization, reducing API load and improving overall sync speed and reliability.
    - [IMP] Improved handling of missing or custom order items. When an order line references a product that no longer exists or represents a custom item and a fallback product is used, the connector now preserves the original product name and SKU from the e-commerce order in the Sales Order Line description.
    - [IMP] Improved automatic cleanup of connector-generated logs. Connector logs (including webhook-related entries) are now cleaned up using a dedicated Odoo cleanup mechanism with a configurable retention period, helping reduce database noise and improve long-term performance.
    - [FIX] Other improvements and fixes implemented to boost overall performance, stability, and reliability.

* 1.13.2 (2025-12-13)
    - [FIX] Fixed an issue with order status export where multiple rapid status changes could be ignored. The connector now creates a separate background job for each status update, ensuring all changes are exported in the correct sequence to the e-commerce store.

* 1.13.1 (2025-11-27)
    - [NEW] Added option to leave the Salesperson field empty on imported Sales Orders. Previously, orders were assigned to Administrator by default. This behavior now matches Odoo's website_sale flow and provides more flexibility for teams that prefer assigning Salespersons manually.
    - [IMP] The "Import Orders" setting is now preserved when Sale Integration is disabled, ensuring the selected value is restored when reactivated. Internal automation checks were also refined for more consistent behavior.
    - [FIX] Fixed an issue in the configuration validation wizard that caused validation to fail when using the Integration Queue Job module (VentorTech fork of Job Queue). The wizard now works correctly with the updated job management logic in Odoo 19.0.
    - [FIX] Order webhooks now correctly respect the "Orders Cut-off Date" setting. Orders created before the cut-off date will no longer be imported or updated when webhook events are received.
    - [FIX] Improved contact matching logic and resolved several edge-case issues that could create duplicate contacts in specific scenarios. Synchronization is now more accurate and consistent.
    - [FIX] Numerous background improvements and fixes implemented to boost overall performance, stability, and reliability.

* 1.13.0 (2025-10-27)
    - [NEW] Redesigned Import Wizard that unifies and simplifies all data import processes. Whether performing an initial setup or importing new records later, users can now follow a clear, step-by-step workflow to bring products, customers, and orders from their e-commerce store into Odoo with ease. This overhaul makes the entire import process faster, more reliable, and beginner-friendly.
    - [NEW] Added “Failed Job Notifications” checkbox on user profiles to control who receives alerts about failed jobs. Enabled by default for users with Job Queue Manager rights.
    - [NEW] Added support for product translations. The connector now synchronizes translations in both directions for key product fields — Name, Description, Meta Title, and Meta Description — making it easier to manage multilingual Shopify stores directly from Odoo.
    - [IMP] Redesigned UI/UX for a smoother, more intuitive experience. Views and menus were reorganized for faster navigation, with new actions, clearer tooltips, and many small visual improvements.
    - [IMP] Improved webhook stability and data accuracy across all connectors. Fixed issues that could cause missing product details and enhanced order webhook logic to respect importable order statuses — preventing unwanted imports of orders in undesired states.
    - [IMP] Improved handling of external fulfillments and payments from e-commerce stores. These records are now applied not only during automated workflows but also when users perform actions manually — such as confirming orders or creating invoices in Odoo. This change provides greater flexibility and ensures external data stays synchronized regardless of how the workflow is triggered.
    - [IMP] Enhanced contact matching logic to prevent duplicates. The connector now uses normalized email and phone values when searching for existing Odoo contacts and addresses, significantly reducing the creation of duplicate records during synchronization.
    - [IMP] Status menu visibility is now limited to users with connector configuration access, keeping the interface clean and focused for regular users.
    - [IMP] Expanded automatic retry logic for Shopify API requests. In addition to handling “Too Many Requests” (429) errors, the connector now automatically retries safe operations after temporary network issues or server-side (500) errors, improving reliability and stability of data synchronization.
    - [FIX] Resolved issues with BoM quantity calculations for products using Bills of Materials. The connector now correctly computes stock levels in complex BoM scenarios, ensuring accurate quantity synchronization based on customer feedback.
    - [FIX] Updated sales dashboard analytics to exclude cancelled orders from statistics, ensuring more accurate sales and performance insights.
    - [FIX] Fixed critical issue with image synchronization caused by recent Shopify API changes, where ProductImage IDs were replaced with MediaImage IDs. This update prevents accidental image removals in Shopify products and ensures stable, reliable media synchronization.
    - [FIX] Numerous background improvements and fixes implemented to boost overall performance, stability, and reliability.

* 1.12.2 (2025-07-23)
    - [NEW] Added support for mapping Shopify Order “Source Name” to a custom field in Odoo.
    - [IMP] Improved tax handling: the connector now detects tax-exempt Shopify orders and avoids assigning taxes to order lines in Odoo.
    - [IMP] Enhanced customer language detection: the connector now uses the customer_locale from the order to assign customer language in Odoo, falling back to the store's default if not available.
    - [IMP] Improved order webhook handling: the connector now checks for missing orders and triggers import if needed before processing status updates.
    - [FIX] Resolved issue where delivery notes were not added to PICK transfers in 2-step delivery operations.
    - [FIX] Resolved issue with Invoices API where credit notes and some invoices were not returned when requested by the e-commerce system.
    - [FIX] Over 30 background improvements and fixes implemented to boost overall performance, stability, and reliability.

* 1.12.1 (2025-05-27)
    - [NEW] Added “Default Customer Language” setting under the Customers tab. Automatically assigns the selected language to new Odoo contacts created from Shopify orders.
    - [NEW] Added support for custom tracking URLs: It is possible now to send tracking links with fulfillments in Shopify - even for unsupported carriers - by enabling the new option in the shipping method settings.
    - [NEW] Added advanced attribute mapping: Now it is possible to map values from external order JSON (e.g. order.store_name) to custom fields on Sales Orders and Deliveries. Includes support for optional Python transformations. Configuration is available in debug mode under Sales Orders → Order & Delivery Attribute Import Mapping.
    - [IMP] Refactored all error and warning messages to provide clearer explanations, actionable steps, and configuration guidance. Users can now troubleshoot common issues independently without needing to contact support.
    - [IMP] Improved: updated priority logic for background jobs (How the Connector Prioritizes Background Jobs).
    - [IMP] Improved consistency: all scheduled actions and webhooks are now executed under the OdooBot user.
    - [IMP] Added new Receive webhook gap (sec) setting to delay webhook event processing when needed.
    - [IMP] Added shortcut to external order on Sales Order form.
    - [FIX] Fixed: webhooks now respect product and order import filters set in the connection configuration.
    - [FIX] Fixed issue where product images could be deleted in Odoo when webhooks were active.
    - [FIX] Fixed issues with default customer configuration when customer data is missing.
    - [FIX] Fixed edge cases where customer info was incomplete or missing in imported orders.
    - [FIX] Made several small improvements to enhance overall performance and stability.

* 1.12.0 (2025-03-26)
    - [NEW] Added "Apply External Payments" feature in Shopify connector: introduces a new checkout option that applies external payments during auto-workflow invoice validation. The "Register Payment" step now checks for existing external payments and only adds a new payment if the invoice is partially paid or unpaid, using the payment method from external payments.
    - [NEW] Added new field "E-Commerce Payment Methods" to sale orders in Odoo to store information about all payment methods used for the order in Shopify.
    - [NEW] Added support for synchronization date/datetime metafields in Shopify connector.
    - [NEW] Launched a dynamic sales dashboard that displays key metrics - total sales, order trends, top products, and customer insights (new vs. returning and country stats) - in an intuitive, easy-to-understand format.
    - [NEW] Added "Ignore BoMs for Product Export" checkbox to skip export of components for products with attached Bill of Materials, useful for synchronizing products as simple items without bundles/kits.
    - [NEW] Added support for synchronizing stock levels for products with "Manufacture" BoMs based on component quantities and BOM records; can be enabled via the "Calculate Stock for 'Manufacture' BoMs" checkbox in the Inventory tab.
    - [NEW] Added support for formulas in pricelist items for both regular and sale price synchronization using Odoo pricelists, enabling export of formula-based prices to e-commerce stores.
    - [NEW] Added Getting Started wizard with introduction videos to enhance user experience.
    - [NEW] Added ability to specify default values for "Tag Group", "Account", and "Tax Scope" fields when creating new Odoo taxes via the connector.
    - [NEW] Added automatic tests for orders import and auto-workflow features in connector.
    - [IMP] Improved partial fulfilment logic in Shopify connector to enable fulfillment using changed Odoo locations by matching products in existing fulfilment orders.
    - [IMP] Upgraded ShopifyAPI to version 12.7.0.
    - [IMP] Refactored image synchronization logic to use mappings, improving performance and preventing unnecessary deletion and creation of images.
    - [IMP] Improved contact creation logic by preventing duplicate child address contacts when billing and shipping addresses are identical, writing the address directly on the customer/company contact.
    - [IMP] Added button in debug mode to open product variant from the product templates view for templates with a single product variant.
    - [IMP] Improved customer matching during order creation by performing case-insensitive comparisons for name and surname fields to avoid duplicates (previously applied only for addresses).
    - [FIX] Fixed tests for fulfilment logic in Shopify connector.
    - [FIX] Fixed issue with images preview in product view (Odoo 18.0).
    - [FIX] Fixed issues causing standard Odoo tests to fail due to connectors.
    - [FIX] Fixed issues with real-time stock export during quantity updates using Ventor PRO application.
    - [FIX] Made several small improvements to enhance overall performance and stability.

* 1.11.2 (2024-11-18)
    - [NEW] Added a checkbox to force the application of fiscal positions to imported orders. This ensures accurate tax calculation even when order line taxes differ from product default taxes. By default, the connector will only set the correct fiscal position without recalculating taxes.
    - Added the ability to import orders with a configurable delay. This is useful when you need to wait for payment confirmation or other custom actions before importing orders into Odoo.
    - Resolved the issue where incorrect prices were set on product variants during the initial import from the e-commerce system to Odoo.
    - Resolved payment creation issues that occurred when the "sale_advance_payment" module (allowing payments to be attached directly to sale orders) was installed.
    - Made several small improvements to enhance overall performance and stability.

* 1.11.1 (2024-09-19)
    - NEW! Added option to set "Compare At" price in Shopify using a specified pricelist during product export.
    - Resolved the issue where incorrect pricelist and currency were set for imported orders.
    - Resolved the issue with the website_sale module dependency in Odoo 17.0.
    - Resolved the issue related to exporting images for templates with variants that are excluded from synchronization.
    - Improved customers import: The connector will use default billing information from the e-commerce store during the initial customer import process, if it is available.
    - Made several small improvements to enhance overall performance and stability.

* 1.11.0 (2024-08-02)
    - NEW! Added the ability to process orders from guests who haven't created an account on e-commerce store.
    - NEW! Added support for partial fulfillments for Shopify orders. Connector now can apply already fulfilled items during order import from Shopify to Odoo, as well as update Shopify order based on transfers statuses in Odoo.
    - NEW! Added the possibility to cancel Shopify orders directly from Odoo. A special wizard will guide through Shopify's cancellation options, including refunds and reasons.
    - NEW! Added the option to filter orders to import based on sales channels in Shopify.
    - Updated ShopifyAPI package to the latest version (12.6.0).
    - Fixed issues with orders containing fallback or removed products.
    - Resolved deprecation warnings that occurred during tests on Odoo.sh.
    - Corrected incorrect stock quantity updates when using the Internal Transfer feature in Ventor.
    - Made several small improvements to enhance overall performance and stability.

* 1.10.1 (2024-05-18)
    - NEW! Added the option to ignore VAT validation when saving customer information to Odoo (Customers → Ignore VAT validation).
    - NEW! Added the option to disable order total difference correction during order import. This prevents the addition of price difference lines when the order total doesn't match between your e-commerce store and Odoo (Sales Order → Order Total Difference Correction).
    - NEW! Added the option to disable order imports entirely from your e-commerce system to Odoo (Automation Jobs → Enable Order Import).
    - NEW! Introduced the ability to customize customer search during import. The "Search Customer Fields" setting (Testing tab) allows you to specify which fields are used to match customers. (Caution: Incorrect settings could lead to duplicate customers or mismatched orders.)
    - Fixed GraphQL requests for multiple Shopify stores: Resolved an issue where the connector could send requests to the incorrect Shopify store when managing multiple connections.
    - Fixed an issue with applying fiscal positions to imported orders.
    - Resolved a VAT validation problem for non-EU countries.
    - Corrected an error ("You cannot create recursive Partner hierarchies") that occurred in certain scenarios.
    - Improved compatibility with Odoo.sh builds by resolving warnings.
    - Other small improvements and fixes.

* 1.10.0 (2024-04-05)
    - NEW! We've improved how our connector manages customer information coming from your e-commerce system. This includes more flexible contact creation, better address handling, and various optimizations. For more details and examples, including benefits for B2B, see our FAQ.
    - NEW! For B2B customers with a manageable number of clients, we've added the ability to manually map customers between your e-commerce system and Odoo. This provides you with additional control.
    - NEW! You now have the option to designate a specific product as a placeholder for order lines with removed products or custom items, ensuring smoother order processing.
    - NEW! You now have the option to switch between different discount application methods. Choose to add discounts as separate order lines (default), or apply them directly to product lines using the 'Discount' field. This can be set from the 'Add discounts as a separate order line' setting on your integration settings.
    - NEW! Our Shopify connector now supports importing order and customer metafields into Odoo with the ability to choose where to save the values.
    - NEW! We've added support for Shopify product webhooks (create/update/delete), keeping your Odoo product data synchronized with your store.
    - NEW! We've introduced a new post-installation wizard that automatically guides you through the steps needed to ensure your Odoo setup is optimized for our connector. This will help you get up and running quickly and smoothly.
    - We've added a new feature for developers to customize how products are linked between your e-commerce system and Odoo. This allows you to use specific fields other than the default SKU or Barcode for product synchronization. Important Note: This feature is intended for developers with a technical understanding of Odoo and your e-commerce platform.
    - We've fixed an issue that was preventing product quantities from updating correctly on your e-commerce store when changes were made in the Ventor application.
    - We've resolved an issue where product internal references in Odoo were still being updated after disabling import in the mapping table.
    - We've enhanced how our connector imports categories from your e-commerce store, especially when multiple categories share the same name. This resolves previous errors and ensures more accurate category matching in Odoo.
    - We've resolved a dependency issue in Odoo 17.0 that caused a “TypeError: Model 'product.image' does not exist in registry.” error. Our connector is now fully compatible with the latest Odoo version.
    - We've resolved an issue that prevented updating already mapped products with archived or draft variants. Your product data will now synchronize smoothly from your e-commerce system.
    - We've also made several additional fixes and enhancements for a better overall experience.

* 1.9.3 (2024-02-01)
    - Added compatibility with 2024-01 Shopify API version `(more information). <https://ventortech.atlassian.net/servicedesk/customer/portal/1/article/568688668>`__

* 1.9.2 (2024-01-05)
    - NEW! On odoo.sh when the backup is restored on the staging branch, disable automatic all sales integrations, disable on integrations critical functions (export of products, order statuses, product inventory) and delete webhooks.
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
    - NEW! Add setting for export prices via pricelist from Odoo to PrestaShop. Configurable based on integration. `(watch video) <https://www.youtube.com/watch?v=Q9Hh1okL3bw&ab_channel=VentorTech>`__
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
    - In case it is configured not to download the barcode field from Shopify to Odoo (in Field Synchronization there is no barcode field defined) connector will not analyze external products for duplicated barcodes.
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
    - NEW! Added setting to automatically create products on SO Import in case products doesn’t exist yet in Odoo. Configurable based on integration.

* 1.5.1 (2023-03-23)
    - Fix issue with impossibility to cancel sales order (in some cases) or register payment.

* 1.5.0 (2023-03-13)
    - NEW! Added “Exclude from Synchronisation” settings on the product to exclude specific products and all their variants totally from sync and all related logic (validation, auto-mapping). `(watch video) <https://youtu.be/7zO2y0Q6aS8>`__
    - NEW! Contacts that were created by the connector will have a special Tag with the name of the sales integration it was created from. That allows us to easier find all contacts created from specific integration. `(watch video) <https://youtu.be/0a0r-RDeNag>`__
    - Copy “E-Commerce Payment Method” from Sales Order to the related Customer Invoice.
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
    - NEW! Allow defining which field should be synchronized when sending the stock to the e-commerce system. Allowing 3 options: “Free To Use Quantity“, “On Hand Quantity” and  “Forecasted Quantity”. `(watch video) <https://youtu.be/8c7yw2QT5fY>`__
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
    - When exporting product from Odoo to Shopify use "Product Name" from "E-Commerce Integration" tab if defined, else use regular product name.
    - Added compatibility with 2022-07 Shopify API version (requesting additional access rights 'write_merchant_managed_fulfillment_orders' and 'write_orders').
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
