ZPL Label Designer
========================


Change Log
##########

|

* 2.0.0 (2026-06-02)
    - [NEW] Added support for Python formulas, enabling advanced formatting, data transformations, calculations, and date formatting directly within labels.
    - [NEW] Introduced ZPL Label Designer + PDF Converter for generating PDF versions of ZPL labels.
    - [NEW] Added one-click connection setup between Odoo and the Designer server, automatically filling in all required settings.
    - [NEW] Added the ability to configure default labels in the "Print Labels" wizard, including both standard Odoo labels and labels created with ZPL Label Designer (via Odoo Direct Print PRO + ZPL Label Designer PRO module).
    - [IMP] Rebuilt the designer interface with a modern, mobile-friendly user experience.
    - [IMP] Added visual label previews in the labels list, making it easier to identify and select the correct label.
    - [IMP] Improved the label deletion workflow.
    - [IMP] Refactored API key validation logic to further reduce the risk of sensitive data exposure.
    - [FIX] Added support for using computed fields in ZPL Label Designer (Odoo 19.0 only).
    - [FIX] Improved overall performance, stability, and reliability.

* 1.3.5 (2026-03-02)
    - [IMP] Improved compatibility with Odoo 19 and integration with Direct Print.
    - [FIX] Fixed minor internal issues to improve overall reliability.

* 1.3.4 (2026-01-28)
    - [NEW] Added support for Data Matrix barcodes.
    - [NEW] Allowed regular users (not only managers) to print ZPL labels.
    - [IMP] Moved the ZPL Label Designer setting to the company level.
    - [IMP] Improved image rendering quality and image compatibility on labels.

* 1.3.3 (2025-04-18)
    - [NEW] Added possibility to print ZPL labels for Workorder (Print Labels button).
    - [NEW] Added a "Duplicate label" button in the designer.
    - [NEW] Added support for Report Rules to define the default printer for "Print Labels".
    - [IMP] Reworked allowed-models storage with automatic data migration.
    - [IMP] Added a quality check for label mapping.
    - [FIX] Fixed minor issues.

* 1.3.2 (2024-04-12)
    - [NEW] Added support of printing custom ZPL labels for product lots in "Print Labels" wizard on transfers.
    - [FIX] Fixed printing of label lines with lots.

* 1.3.1 (2024-03-20)
    - [NEW] Allowed nested labels to be stacked vertically.
    - [NEW] Added ReCAPTCHA to registration, password-restore and resend-confirmation.
    - [IMP] Show the technical field name in the "Add Nested Label" dialog.
    - [FIX] Fixed issue with selection of custom ZPL Labels in "Print Labels" wizard on transfers.
    - [FIX] Fixed issue with missing fields in label preview.

* 1.3.0 (2023-04-16)
    - [NEW] Added support for many2many and one2many fields.
    - [FIX] Fixed publishing of labels containing images, special symbols and centered text.

* 1.2.0 (2023-02-23)
    - [NEW] Moved designer to a separate UI: labels.ventor.tech.
    - [NEW] Migrated to a new framework (Konva.js).
    - [NEW] Added support for different encodings.
    - [NEW] Added possibility to change barcode and QR code size.
    - [NEW] Added possibility to change font size.
    - [FIX] Fixed some small issues that were affecting the user experience.

* 1.1.0 (2022-12-06)
    - [NEW] Added possibility to render lines.
    - [NEW] Added possibility to select models to be used while creating labels (in module Settings).
    - [NEW] Added possibility to select nested fields to add to the label.
    - [NEW] Added snap feature to simplify the positioning of elements.
    - [NEW] Added grid feature (can be enabled/disabled with special checkbox).
    - [FIX] Fixed issue with duplicating labels.
    - [FIX] Fixed odoo.sh warnings while installing the module.
    - [FIX] Fixed issue with rotation of barcodes.
    - [FIX] Fixed issue with compatibility with Direct Print for Odoo 15.0.

* 1.0.0 (2022-09-05)
    - [NEW] Initial version of module.

|
