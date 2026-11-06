Changelog
=========

v18.0.11.2.0 (2026-10-28)
-------------------------
* error count and position in the file for each XML validation error, ref #20227
* namespace prefixes in validation errors also for files with a default namespace, ref #20227
* faster XML validation, ref #20227

v18.0.11.1.1 (2026-10-28)
-------------------------
* fix Greek (`EL`) VAT prefix in `x_get_eu_vat`, ref #11675
* use `EL` instead of `GR` for Greece in EU VAT numbers
* `x_get_country_by_code` no longer caches a recordset
* add missing translations of VAT validation errors, drop the unused one
* remove unused import
* clear message when the file does not match the document type, ref #20227

v18.0.11.0.1 (2026-10-02)
-------------------------
* R17 sync
  * use local tax offices schema (v8) to load data instead of network
  * add `x_invoice_sale_date` fallback to date
  * fix GTU update on move lines (update after creation, once `display_type` is populated)
  * fix MPP rounding (compare the converted amount using the target currency's precision)
  * fix stale VAT validation cache: `x_get_eu_vat`/`x_get_eu_vat_country`/`x_get_pl_vat` now key on the actual
    VAT/country values, not just the record, so an edited VAT number is revalidated instead of reusing an old result
  * fix stale XLSX styles cache across report generations, and a row/column mixup in `_write_cell`'s merge range
  * `ir.attachment`: drop `x_size` in favour of the core `file_size` field, `x_get_full_path` now raises a clear
    error instead of crashing when the attachment isn't stored on the filesystem
  * disable network access and external entity resolution when validating uploaded XML (XXE hardening)
  * fix Polish street splitting for names containing digits (e.g. "ul. 3 Maja 12")
  * `jpk.account.tag` CRUD restricted to accounting managers, regular accountants keep read-only access
  * fix JPK XLSX report download missing the user context when no wizard options are present
  * removed the redundant `_get_report_from_name` override
  * code cleanup
* fix XLSX report crash - refactor style handling, ref #11675-257

v18.0.10.0.0 (2026-09-21)
-------------------------
* R17 sync
  * update XML Schema validation, XML Schema documents are read from module files instead of the database
  * add local XML dependencies - no external call to MF servers
  * add FA(3) KSeF XML Schema
* BREAKING: `jpk.document.type` `xsd_id`, `xsd_id_name`, `xsd_id_datas` fields removed in favour of `schema_path`
  and `is_valid_xml` replaced by `validate_xml`

v18.0.9.0.1 (2026-09-10)
------------------------
* `S_12_1` and `S_12_2` account tags, ref #19285
* reject foreign VAT prefixes in x_get_pl_vat, ref #19613 #19679

v18.0.8.0.3 (2026-09-01)
------------------------
* document type schema validation, ref #19233
* better handle & validate PL VAT numbers, ref #19336
* fix `x_get_eu_vat` and `x_get_pl_vat` + move fixed vat methods from `trilab_jpk_vat`, ref #19335
* update vat sanitize, ref #19335

v18.0.7.2.2 (2026-07-30)
------------------------
* add JPK_V7M (3) 1.0E XSD
* R19 backports
* code cleanup
* better handle & validate EU VAT numbers, ref #19233

v18.0.7.1.0 (2026-07-13)
------------------------
* fix `x_get_pl_vat` treating foreign VAT numbers as Polish NIP for PL-addressed partners, ref #19075

v18.0.7.0.0 (2026-06-15)
------------------------
* KSeF invoice number validation, ref #18468

v18.0.6.5.1 (2026-05-23)
------------------------
* update V7M(3) XSD, ref #18448
* revert update V7M(3) XSD, ref #18448

v18.0.6.4.0 (2026-05-11)
------------------------
* do not copy x_pl_ksef_invoice_proof, ref #18328

v18.0.6.3.1 (2026-04-13)
------------------------
* sundown ir.attachment extra fields
* fix cache syntax, ref #17464

v18.0.6.2.0 (2026-04-01)
------------------------
* non-readonly TP tag on in invoice/in refund view, ref #17529

v18.0.6.1.0 (2026-02-20)
------------------------
* cleanup
* add KSeF filters
* move resequence wizard menu action, ref #11675
* update x_pl_ksef_invoice_proof readonly logic, ref #17520

v18.0.6.0.0 (2026-02-09)
------------------------
* journal entry number with resequence, ref #11675
* add document type `JPK_KR_PD(1) v1-1`, ref #11675

v18.0.5.0.0 (2026-02-09)
------------------------
* add document type `JPK_ST_KR(1) v1-0`, ref #11676

v18.0.4.1.0 (2026-01-19)
------------------------
* TP tag on in invoice/in refund view, ref #16719

v18.0.4.0.0 (2026-01-19)
------------------------
* add document type `JPK_V7M (3) 1-0E`, ref #16581

v18.0.3.0.0 (2025-10-25)
------------------------
* test EU VAT id independent of partner country, ref #15871
* fix prevent copying vat date on invoice duplicate, ref #16414
* fix GTU assignment on account move line, ref #16458
* io buffer optimizations

v18.0.2.0.0 (2025-07-25)
------------------------
* change translation, ref #14551
* bump version

v18.0.1.0.0 (2025-02-25)
------------------------
* initial R18, ref #11973
* do not copy vat date
