# -*- coding: utf-8 -*-
import math

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_round

LABEL_TYPES = [
    ("quant", "Stock Label (without qty)"),
    ("product", "Stock Label"),
    ("both", "Both Labels"),
]


class MrpLabelPrintWizard(models.TransientModel):
    _name = "mrp.label.print.wizard"
    _description = "MO Labels Print Wizard"

    production_ids = fields.Many2many(
        "mrp.production", string="Manufacturing Orders", readonly=True
    )
    line_ids = fields.One2many(
        "mrp.label.print.wizard.line", "wizard_id", string="Lines"
    )
    total_label_qty = fields.Integer(
        compute="_compute_total_label_qty", string="Total Labels"
    )
    is_multi_production = fields.Boolean(compute="_compute_is_multi_production")
    label_type = fields.Selection(
        LABEL_TYPES,
        string="Label",
        required=True,
        default="both",
        help="Label template set for all lines, it can be changed per line afterwards.",
    )

    @api.depends("line_ids.label_qty", "line_ids.label_type", "line_ids.quant_id")
    def _compute_total_label_qty(self):
        for wizard in self:
            wizard.total_label_qty = sum(
                line.label_qty * (2 if line.label_type == "both" else 1)
                for line in wizard._get_printable_lines()
            )

    @api.depends("production_ids")
    def _compute_is_multi_production(self):
        for wizard in self:
            wizard.is_multi_production = len(wizard.production_ids) > 1

    @api.onchange("label_type")
    def _onchange_label_type(self):
        if self.label_type:
            for line in self.line_ids:
                line.label_type = self.label_type

    def _get_printable_lines(self):
        """Labels are printed only for lines with a quant."""
        return self.line_ids.filtered(lambda l: l.quant_id and l.label_qty > 0)

    def action_print(self):
        self.ensure_one()
        if not self._get_printable_lines():
            raise UserError(self.env._("There are no labels to print."))
        return self.env.ref(
            "efarmer_mrp_label_print.action_report_mrp_label_print"
        ).report_action(self)


class MrpLabelPrintWizardLine(models.TransientModel):
    _name = "mrp.label.print.wizard.line"
    _description = "MO Labels Print Wizard Line"
    _order = "production_id, line_type desc, id"

    wizard_id = fields.Many2one(
        "mrp.label.print.wizard", required=True, ondelete="cascade"
    )
    production_id = fields.Many2one("mrp.production", string="MO", readonly=True)
    line_type = fields.Selection(
        [("component", "Component"), ("finished", "Finished Product")],
        string="Type",
        readonly=True,
    )
    product_id = fields.Many2one(
        "product.product", string="Product", required=True, readonly=True
    )
    lot_id = fields.Many2one("stock.lot", string="Lot/Serial Number", readonly=True)
    location_id = fields.Many2one("stock.location", string="Location", readonly=True)
    quant_id = fields.Many2one("stock.quant", string="Quant", readonly=True)
    quantity = fields.Float(
        string="Quantity", digits="Product Unit of Measure", readonly=True
    )
    product_uom_id = fields.Many2one(related="product_id.uom_id", string="UoM")
    label_type = fields.Selection(
        LABEL_TYPES,
        string="Label",
        required=True,
        default="both",
    )
    label_qty = fields.Integer(string="Labels Qty")

    @api.model
    def _get_default_label_qty(self, product, qty):
        if product.tracking == "serial":
            return int(float_round(qty, precision_digits=0))
        qty = float_round(qty, precision_rounding=product.uom_id.rounding)
        return math.ceil(qty)

    def _get_label_docs(self):
        """Return list of (template, records) to render, records are repeated label_qty times."""
        self.ensure_one()
        res = []
        if not self.quant_id:
            return res
        if self.label_type in ("quant", "both"):
            res.append(("efarmer_sale_workflow.stock_quant_without_qty", self.quant_id))
        if self.label_type in ("product", "both"):
            res.append(
                ("efarmer_sale_workflow.stock_label_product_product", self.product_id)
            )
        return [
            (template, record.browse([record.id] * self.label_qty))
            for template, record in res
        ]
