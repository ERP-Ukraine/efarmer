Changes
~~~~~~~

v15.0.3.0.0 (2026-03-16)
------------------------
* remove `ksef.tax.tag`, ref #17318-25
* update zero tax base amount logic to use `ksef.tax.amount` instead of `tax.tag`, ref #17318-26
* remove `required` view attr for `x_ksef_p_19X`, ref #16782
* fix `_x_ksef_build_tp`, ref #16782
* fix typing collections, ref #17569
* improve error handling by resetting state key on failure cases, ref #17440
* fix zero tax base amount logic, ref #17318-43
* refactor `_x_ksef_get_tax_base_amount` to use Generator expression instead of `filter`, ref #17440

v15.0.2.0.0 (2026-03-02)
------------------------
* refactor Vendor Invoice XML parsing to use `XMLParser`, ref #17120
* fix invoice visualization, ref #17357 #17345
* fix payment term form view, ref #17109-41
* fix `_x_ksef_is_vendor_bill_xml`, ref #16782-39
* fix `_x_ksef_import_vendor_invoice` and fix markup usage, ref #16782-39
* fix parsing warnings, ref #17440
* fix currency rate field, ref #17440
* fix manual saving `x_pl_ksef_invoice_number`, ref #17109 #17440
* remove default value for `P_8A` and `P_8AZ`, ref #17440-9
* add handling for `TP` tag, ref #17440-9
* fix price unit parsing, ref #17522
* fix currency rate field on invoice lines, ref #16572-110

v15.0.1.1.0 (2026-02-08)
------------------------
* refactor `x_ksef_invoice_date_applicability` logic - remove enterprise dependency, ref #8078, #17010
* fix VAT EU value extraction logic, ref #16927-66
* fix tax computation by normalizing quantity sign, ref #17055
* fix invoice line error translation format values, ref #17077
* adjust visibility of `x_ksef_invoice_date_applicability`, ref #17059-2
* fix order date insertion logic in KSeF EDI processing, ref #16624-52
* make KSeF disabled by default on journals, ref #17113
* fix visualization, ref #16456-79
* fix price unit and annotation on visualization, ref #16456-85
* fix qr code generation and text formatting, ref #16456
* set `pl_vat_date` from parsed `DataWytworzeniaFa`, ref #17100-10
* set `is_company` flag in partner data by default, ref #17167
* disable onchange name predictive in `_update_invoice_from_attachment`, ref #17147-8

v15.0.1.0.0 (2026-02-01)
------------------------
* initial release R15, ref #16782
* fix `_x_ksef_is_vendor_bill_xml`, ref #16547
* refactor KSeF authentication handling, improve error management, ref #16925
* refactor invoice line filtering with `x_ksef_get_invoice_line_ids`, ref #16929
* fix client, ref #16927
* fix `ir.attachment` access permissions, ref #16965
* make `x_ksef_purchase_journal_id` company-dependent, ref #16994
* fix `ir.attachment` access permissions for Invoice report, ref #16965-6
* improve error handling and retry logic for KSeF API rate limits, ref #17006
* adjust logging levels for KSeF API rate limit handling, ref #17006
* refine transaction conditions handling for invoices with `invoice_ref`, ref #16927-56
