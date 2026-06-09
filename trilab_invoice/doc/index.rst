Changelog
=========

v18.0.3.1.1 (2026-04-21)
------------------------
* stop partner bank recompute for corrections, ref #17554
* move company partner bank on pro-forma checkbox to TI settings, ref #17967

v18.0.3.0.0 (2026-04-16)
------------------------
* company partner bank on pro-forma invoice, ref #17967

v18.0.2.3.0 (2026-03-29)
------------------------
* keep existing invoice narration for currency invoices
* code cleanup
* further invoice currency rate simplifications - keep original calc on no-ti companies, ref #17140
* partial reverse of upstream sync changes, ref #17524 #17733
* hide spare totals table on advance/final/correction invoice report, ref #17156

v18.0.2.2.0 (2026-03-26)
------------------------
* skip reverse invoice reconcile visible to all companies, ref #17524 #17270-36

v18.0.2.1.0 (2026-03-17)
------------------------
* simplify invoice currency rate computations, ref #17140

v18.0.2.0.0 (2026-03-14)
------------------------
* add option to skip reverse invoice reconcile, ref #17524
* update methods to reflect upstream changes

v18.0.1.6.0 (2026-02-24)
------------------------
* fix correction invoice lines, ref #17244
* sync with base odoo code, ref #16187
* fix override, ref #17344
* fix amount to text lang in template preview, ref #14250
* fix `_compute_amount_currency`, ref #17400

v18.0.1.5.0 (2026-02-11)
------------------------
* add payment communication to out refund invoice report, ref #16968
* fix advance invoice wizard `constrains_values`, ref #17040 #17111

v18.0.1.4.0 (2025-11-11)
------------------------
* prevent sale / currency date copy on invoice duplicate, ref #16038
* remove tax code from Downpayment Invoice Line name, ref #15664
* fix prevent copying sale and currency date on invoice duplicates, ref #16414
* fix currency recalc, ref #16388
* fix anglo saxon price unit - price_unit rounding errors, ref #16512
* fix `x_corrected_invoice_line_ids` lines filtering, ref #16105-10

v18.0.1.3.0 (2025-08-07)
------------------------
* adjust invoice report, ref #14551
* paid amount on advance/final/correction invoice report, ref #13596
* fix invoice currency rates + final invoice price unit, ref #14755
* fix final invoice price unit + journal entry line currency rate, ref #11806-117
* code cleanup
* fix x_use_ti compute method, ref #16018

v18.0.1.2.0 (2025-08-05)
------------------------
* change translation, ref #14551
* add reverse charge on invoice report, ref #14551

v18.0.1.1.0 (2025-07-03)
------------------------
* fix _stock_account_get_anglo_saxon_price_unit, for invoice after correction, ref #14491
* fix tax invoice label, ref #13913
* fix journal entry multi currency, ref #11806

v18.0.1.0.0 (2025-01-21)
------------------------
* initial R18
* translations fix, ref #12841
* restore standard purchase refunds, ref #12261
* fix _apply_price_difference, for correction invoices, ref #12261, ref #13568
* layouts fix, ref #13499
* handle invoice wizard for different partners, ref #13627
* fix x_action_reverse_pl btn invisible domain, ref #13734
* fix advance payment lang selection, ref #13014
* fix advance correction invoice summary, #13499
* fix advance correction invoice summaries, #13499
* tax amount column on advance invoice report, ref #13913
* delete sale order summary on invoice report, ref #13913
* fix amount in words translation, ref #13499
