Changelog
=========

v18.0.7.3.0 (2026-04-21)
------------------------
* refactor header generation, ref #16572

v18.0.7.2.1 (2026-04-21)
------------------------
* add opt-out flag `x_ksef_disable_shipping_third_party` for shipping address as third party, ref #17997
* warn on refund missing `reversed_entry_id`, skip auto-send to KSeF, ref #17953-10
* add `GLN` and `EORI` fields support for partners, ref #17997-8
* fix Invoice narration length limit, ref #17997-9
* add support for `IDWew` - `x_ksef_internal_id`, ref #17997-8
* derive JST/GV buyer flags from third party classifications, ref #17997-8
* fix use of `x_get_pl_vat`, ref #17631
* handle validation errors inside `_x_ksef_create_report_attachment`, ref #17631

v18.0.7.1.0 (2026-04-17)
------------------------
* seller contact info, ref #16572

v18.0.7.0.1 (2026-04-16)
------------------------
* feat: replace KSeF-specific P_18/P_18A/P_23 with shared VAT fields, ref #17435
* fix reset-to-draft, ref #17837-23 #17032

v18.0.6.3.2 (2026-04-15)
------------------------
* feat: generate KSeF XML from Send wizard, block reset to draft when XML exists, ref #17837-4
* fix: wrap KSeF auth state `set_param` in savepoint to prevent transaction abort on lock conflict, ref #14307-116
* fix: correct sign and delta in _x_ksef_get_zero_tax_base_amount for correction invoices, ref #17750-2
* fix KSeF XML generation from Send wizard, ref #17837
* replace hard reset-to-draft block with confirm dialog, ref #17837-23
* sort invoice lines in x_ksef_get_invoice_line_ids, ref #17837
* fix fields label conflict

v18.0.6.2.2 (2026-04-10)
------------------------
* fix `x_ksef_notify_admins` permissions issue, ref #17857
* parse `P_10` - `discount` field at `_x_ksef_parse_invoice_line`, ref #17826
* add `ksef_unlink_to_send_edi_documents` action, #14666-5
* add `x_ksef_enable_outgoing_stock_pickings` to sale invoices, ref #17804
* add `_x_ksef_post_process_invoice_xml` for XML invoice customization, ref #17796
* add logic for handling discounts as amounts, ref #17918
* refactor precision handling for invoice lines, ref #17927
* enhance `_x_ksef_amount_repr` to handle trailing zeros, ref #17927

v18.0.6.1.5 (2026-04-08)
------------------------
* add resend to KSeF button, ref #17776
* fix VAT date parsing, ref #17769
* add partner matching by company context, ref #17741
* remove reporting of zero amounts for missing tax values, #16650
* restore settings view
* public changelog
* truncate XML invoice fields, ref #17809
* fix `_x_ksef_get_third_parties` to handle nullable `partner_shipping_id`, ref #17854
* make `_truncate` strip values, ref #17809
* fix `_x_ksef_build_third_parties` TIN country code, ref #17879
* refactor `_x_ksef_get_tax_base_amount` tax groups filtering
* add `ksef.third_party` access rights for partner manager and salesman, ref #17756

v18.0.6.0.0 (2026-04-02)
------------------------
* add support for KSeF third-party management on invoices and orders, ref #17632
* limit P_7Z field, ref #17775
* ensure country code, ref #17753

v18.0.5.2.0 (2026-03-27)
------------------------
* fix providing invoice correction reason as OrderNumber, ref #17628, #14307-55
* fix correction handling in `_x_ksef_get_zero_tax_base_amount`, ref #17628, #14307-55
* add support for buyer contact information on invoices, ref #17628, #17564-27
* add handling for due date extraction from `TerminPlatnosci`, ref #17628, #17534-25
* make `P_6` conditional based on `P_6A`, ref #16572-169
* prevent from checking batch invoice status for not eligible invoices, ref #17685-41
* fixed an issue where invoices were resent due to double posting, ref #17685-41
* refactor session invoice handling to use `get_all_session_invoices` for paginated data retrieval, ref #17685-47
* fix tin vat fallback - use `vat` or `company_registry` for TIN field, ref #17739
* fix `x_ksef_generate_qr_code_url_pair` - add `ensure_one()` and guard against missing invoice date, ref #16881
* fix purchase journal resolution to use partner in correct company context, ref #17741
* fix _x_ksef_get_vendor_partner_id, ref #17744
* fix invoice visualization, ref #17740

v18.0.5.1.0 (2026-03-19)
------------------------
* improve error handling - notify admins on import/export errors, ref #16927-94
* improve error handling by resetting state key on failure cases, ref #17440
* fix zero tax base amount logic, ref #17318-43
* refactor `_x_ksef_get_tax_base_amount` to use Generator expression instead of `filter`, ref #17440
* move discount column header, ref #17698
* fix invoice link truncation on KSeF invoice visualization, ref #17702

v18.0.5.0.0 (2026-03-16)
------------------------
* remove `ksef.tax.tag`, ref #17318-25
* update zero tax base amount logic to use `ksef.tax.amount` instead of `tax.tag`, ref #17318-26

v18.0.4.1.0 (2026-03-11)
------------------------
* add fallback purchase journal support and improve vendor invoice parsing logic, ref #17265
* remove default value for `P_8A` and `P_8AZ`, ref #17440-9
* add handling for `TP` tag, ref #17440-9
* fix price unit parsing, ref #17522
* fix currency rate field on invoice lines, ref #16572-110

v18.0.4.0.0 (2026-03-02)
------------------------
* refactor Vendor Invoice XML parsing to use `XMLParser`, ref #17120
* fix required for P_19 fields in account.move view, ref #16927-78
* fix invoice visualization, ref #17357 #17345
* fix `_x_ksef_get_invoice_payments_data` - ignore exchange diff payments, ref #17391
* fix parsing warnings, ref #17440
* fix currency rate field, ref #17440

v18.0.3.0.0 (2026-02-11)
------------------------
* refactor KSeF XML serialization to use `lxml.builder.ElementMaker`, ref #17011
* replace mail activity with channel message, ref #17011
* fix invoices in currency, ref #16833
* fix invoice reverse currency rate, ref #16833
* add sections for visualization, ref #16706 #17079 #17134
* fix visualization, ref #16456-79
* fix price unit and annotation on visualization, ref #16456-85
* fix post of ti & non-ti entries in same call, ref #17194
* fix qr code generation and text formatting, ref #16456
* set `pl_vat_date` from parsed `DataWytworzeniaFa`, ref #17100-10
* set `is_company` flag in partner data by default, ref #17167
* disable onchange name predictive in `_extend_with_attachments`, ref #17147-8

v18.0.2.2.0 (2026-02-08)
------------------------
* refactor `x_ksef_invoice_date_applicability` logic - remove enterprise dependency, ref #8078, #17010
* fix VAT EU value extraction logic, ref #16927-66
* fix tax computation by normalizing quantity sign, ref #17055
* fix invoice line error translation format values, ref #17077
* adjust visibility of `x_ksef_invoice_date_applicability`, ref #17059-2
* fix order date insertion logic in KSeF EDI processing, ref #16624-52
* make KSeF disabled by default on journals, ref #17113

v18.0.2.1.0 (2026-01-31)
------------------------
* add add production keys and settings for KSeF, ref #8078
* fix relative XML paths in vendor bill import logic, ref #8078-416
* enhance KSeF batch handling logic with sync date tracking, ref #8078-416
* fix partner name, ref #16927
* fix `_x_ksef_is_vendor_bill_xml`, ref #16547
* refactor KSeF authentication handling, improve error management, ref #16925
* refactor invoice line filtering with `x_ksef_get_invoice_line_ids`, ref #16929
* import + client fix, ref #16547
* fix warning, ref #16927
* fix `ir.attachment` access permissions, ref #16965
* make `x_ksef_purchase_journal_id` company-dependent, ref #16994
* fix `ir.attachment` access permissions for Invoice report, ref #16965-6
* improve error handling and retry logic for KSeF API rate limits, ref #17006
* adjust logging levels for KSeF API rate limit handling, ref #17006
* refine transaction conditions handling for invoices with `invoice_ref`, ref #16927-56
* fix `x_ksef_purchase_journal_id` migrations, ref #16917

v18.0.2.0.0 (2026-01-26)
------------------------
* public release, ref #8078
* fix partner vat lookup at `_x_ksef_import_vendor_invoice`, ref #8078-384
* fix invoice correction amounts, ref #8078-384
* allow to import correction invoices, ref #8078-384
* specify `date_type` as `PermanentStorage` for import vendor invoices, ref #8078-389
* enhance batch import to include descriptive message for imported invoices, ref #8078-396
* introduce KSeF admin activity for authentication errors, ref #8078-396
* add support for KSeF payment state mapping, ref #16690-10
* add `cron_check_invoice_status` and refactor related methods, ref #16690-10
* add `ksef.batch.import.wizard`, ref #16690-10

v18.0.1.2.0 (2026-01-19)
------------------------
* replace `x_ksef_invoice_number` with `x_pl_ksef_invoice_number`, ref #16581
* fix default value, ref #8078-362
* add default invoice date applicability setting, ref #16543-30
* add `ksef.settings` action and menu, ref #8078
* add `qr_code_url` to `ksef.settings` views, ref #8078

v18.0.1.1.0 (2026-01-16)
------------------------
* invoice visualization, ref #16456
* fix invoice visualization, ref #16456
* fix `_x_ksef_build_correction`, ref #8078-324
* set `pl_vat_date` from `P_1`, ref #8078-324
* render KSeF `report_invoice` on import, ref #8078-324
* cleanup client class and add `build_certificate_verification_url`, ref #8078-328
* add ksef qr code type II`, ref #8078-328

v18.0.1.0.0 (2025-10-26)
------------------------
* initial release R18, ref #8078, # 15785
* add Vendor Bills import from KSeF, ref #8078
* fix KSeF EDI content generation, ref #8078-150
* add KSeF Vendor Bills import Annotations, ref #8078
* refactor batch export to import, ref #8078-165
* improve tax error messages for clarity, ref #8078-156
* add demo environment configuration and keys, ref #8078-178
* add x_ksef_payment_term_type field, ref #8078-173
* add mapping for payment terms and partner bank details in KSEF XML generation, ref #8078-173
* add GTU field mapping in KSEF XML generation, ref #8078-173
* add new invoice types support, ref #8078-173
* add partner validation for KSeF applicability (require company or VAT), ref #8078-221
* add refund validation (reversed entry and line count matching), ref #8078-221
* add FP support for document type, ref #8078-221
* fix bank account XML element order (`SWIFT` before `NazwaBanku`), ref #8078-221
* add invoice reference support in transaction conditions, ref #8078-221
* add partner field for custom KSeF purchase journal configuration, ref #8078-221
* fix Invoice Report to display KSeF invoice number correctly, ref #8078-221
* add batch invoice import to KSeF, ref #8078-235
* add Invoice verification QR code generation, ref #8078-235
* fix report invoice, ref #8078
* add `x_ksef_invoice_date_applicability`, ref #16543-10
* add `x_ksef_amount`, ref #8078-273
* fix `_x_post_wo_validation` - edi integration, ref #8078
* extend `_x_ksef_build_payment` - support invoice payment state, ref #8078
