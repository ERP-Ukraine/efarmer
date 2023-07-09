Ventor Base
=========================

Base module that allow relation between Ventor modules

Changelog
---------

15.0.1.8.0 (2023-06-26)
***********************

* Added the setting 'Force pack' to the Package Management menu
* Added the setting 'Show quantity dialog first' to the Create SO and Create PO menus
* Added Wave Picking Menu
* Renamed the "Force destination package scan“ setting to “Confirm destination package“
* Added setting “Use reusable packages“ to Cluster picking menu

15.0.1.7.0 (2023-03-06)
***********************

* Added RFID menu
* Added the barcode of the Sale order name to the Picking Operations report for outgoing transfers
* Added 'Order Recheck' menu

15.0.1.6.0 (2022-12-23)
***********************

* Added the setting 'Save transfer after exit' to the Internal Transfers menu
* Added the setting 'Allow creating new packages' to menus Instant Inventory, Batch Picking, Cluster Picking, Internal Transfers, and all Operation Types
* Added the ability to move pallets

15.0.1.5.0 (2022-10-10)
***********************

* Added the setting 'Start inventory with 1' to Instant Inventory
* Added the setting 'Hide Qty to receive ' to  Types of Operations is Receipt
* Added ability to check Custom Build Name for all devices from Odoo side value
* Added Ventor Settings menu with submenu:
    Warehouse Opration
    Package Management
    Batch Picking
    Cluster Picking
    Internal Transfers
    Putaway
    Instant Inventory
    Quick Info
    Scrap Management

15.0.1.4.0 (2022-06-08)
***********************

* Added group 'Validate Inventory'
* Added warning note in user settings about field 'Allowed Warehouses'
* Fixed uploading Custom Mobile Logo
* Renamed name of fields in Ventor Configuration:
    Apply default lots -> Apply default lots and serials
    Transfer more items -> Move more than planned
    Autocomplete the item quantity field -> Autocomplete item quantity
    Manage packages -> Show packages fields
    Scan destination package -> Force destination package scan
    Manage product owner -> Show Product Owner field
* Added the setting 'Confirm source package' to all Operation Types and dependency on the general 'Package' setting
* Added 'Apply default lots and serials' dependency on 'Lots & Serial Numbers'
* Added automatic switch on the 'Show Put in pack button' setting in all menus to default if setting "Package" is switched on
* Added automatic switch on the 'Show Product Owner field“' setting in all menus to default if setting "Consignment" is switched on

15.0.1.3.9 (2022-04-27)
***********************

* Changed name of the group from 'Manufacturing Menu' to 'MO and WO management'
* Added record rule 'See Stock Quant Package from allowed warehouses' for restricting access to warehouses for odoo users

15.0.1.3.8 (2022-02-03)
***********************

* Added security group 'Warehouse Operations: Allow applying all qty of product'
* Added automatic switch on the 'Manage package' setting in all menus to default if setting 'Package' is switched on
* Added the setting “Scan destination location” to all Operation Types
* Added dependency of settings 'Show next product' and 'Confirm product'
* Added the settings 'Behavior on split operation' and 'Behavior on backorder creation' to all Operation Types
* Added sudo rules for validating stock picking in transit
* Added post init hook and migration for setup Allowed Warehouses to users

15.0.1.3.7 (2021-12-2)
***********************

* [REM] Removed unused settings displayed in the Ventor Preferences tab on the user form
* [REM] Removed 'Default inventory location' from the Inventory settings from the Ventor Configuration
* [IMP] Changed 'Ventor Configuration' menu, added 'User Settings' menu item
* [REM] Removed 'Custom package name' field displayed in the Ventor Preferences tab on the user form
* [IMP] Added 'Custom Build Name' field in Ventor Configuration/Additional Settings
