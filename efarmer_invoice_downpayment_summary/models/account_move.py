from odoo import models

DP_SUMMARY_REPORT = "efarmer_invoice_downpayment_summary.report_invoice_document"


class AccountMove(models.Model):
    _inherit = "account.move"

    def _get_name_invoice_report(self):
        self.ensure_one()
        if self._ef_has_downpayment_summary():
            return DP_SUMMARY_REPORT
        return super()._get_name_invoice_report()

    def _ef_has_downpayment_summary(self):
        """Final customer invoice with deducted down payments of a company
        that doesn't print with the Trilab report (FB)."""
        self.ensure_one()
        return not self.company_id.x_use_ti and bool(self._ef_get_downpayment_lines())

    def _ef_get_downpayment_lines(self):
        """Down payment lines deducted on this invoice. On a standalone
        advance invoice they are what is invoiced, so they don't count."""
        self.ensure_one()
        if self.move_type != "out_invoice" or self._is_downpayment():
            return self.env["account.move.line"]
        return self.invoice_line_ids.filtered(
            lambda line: line.display_type == "product" and line.is_downpayment
        )

    def _ef_split_invoice_lines(self):
        """Printed invoice lines split into (product part, down payment part).

        Odoo puts the down payment lines at the end of a final invoice, right
        after their "Down Payments" section, which has no down payment flag, so
        the split is made at the first deduction line, taking along the
        section just before it.
        """
        self.ensure_one()
        # same order as account.report_invoice_document
        lines = self.invoice_line_ids.sorted(
            key=lambda line: (-line.sequence, line.date, line.move_name, -line.id), reverse=True
        )
        dp_lines = self._ef_get_downpayment_lines()
        split_index = next(
            (index for index, line in enumerate(lines) if line in dp_lines), len(lines)
        )
        if split_index and lines[split_index - 1].display_type == "line_section":
            split_index -= 1
        return lines[:split_index], lines[split_index:]

    def _ef_split_base_lines(self):
        """Rounded base lines of the invoice (the same ones Odoo uses for
        tax_totals), split into (product lines, down payment lines)."""
        self.ensure_one()
        dp_lines = self._ef_get_downpayment_lines()
        base_lines, _tax_lines = self._get_rounded_base_and_tax_lines()
        product_base_lines, dp_base_lines = [], []
        for base_line in base_lines:
            if base_line["record"] in dp_lines:
                dp_base_lines.append(base_line)
            else:
                product_base_lines.append(base_line)
        return product_base_lines, dp_base_lines

    def _ef_tax_totals(self, base_lines):
        return self.env["account.tax"]._get_tax_totals_summary(
            base_lines=base_lines,
            currency=self.currency_id,
            company=self.company_id,
        )

    def _ef_get_lines_tax_totals(self):
        """Tax totals of the invoiced lines, before deducting down payments.
        Same structure as tax_totals."""
        product_base_lines, _dp_base_lines = self._ef_split_base_lines()
        return self._ef_tax_totals(product_base_lines)

    def _ef_get_applied_downpayments(self):
        """One entry per advance invoice with the amounts deducted on this
        invoice (positive values, taxes of the deduction lines)."""
        self.ensure_one()
        _product_base_lines, dp_base_lines = self._ef_split_base_lines()

        base_lines_by_advance = {}
        for base_line in dp_base_lines:
            advance = base_line["record"]._get_downpayment_lines().move_id.filtered(
                lambda move: move != self and move.state == "posted"
            )
            base_lines_by_advance.setdefault(advance, []).append(base_line)

        result = []
        for advance, base_lines in base_lines_by_advance.items():
            totals = self._ef_tax_totals(base_lines)
            result.append({
                # fallback on the line label "Down payment (Ref: INV/... on ...)"
                "name": ", ".join(advance.mapped("name"))
                or ", ".join(bl["record"].name or "" for bl in base_lines),
                "date": advance[:1].invoice_date,
                "net": -totals["base_amount_currency"],
                "tax": -totals["tax_amount_currency"],
                "gross": -totals["total_amount_currency"],
            })
        return sorted(result, key=lambda dp: (str(dp["date"] or ""), dp["name"]))
