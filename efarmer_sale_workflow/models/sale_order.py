from datetime import datetime
from markupsafe import Markup
from dateutil.relativedelta import relativedelta
from odoo import fields, models, api, _


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _get_default_delivery_term_id(self):
        return self.env["delivery.terms"].search(
            [
                ("default_for_company", "=", True),
                ("company_id", "=", self.env.company.id),
            ],
            limit=1,
        )

    paid_on_date = fields.Date(
        string="Paid on",
    )

    opportunity_stage_id = fields.Many2one(
        comodel_name="crm.stage",
        string="Opportunity Stage",
        related="opportunity_id.stage_id",
        readonly=False,
    )

    state = fields.Selection(
        selection_add=[
            ("to_payment", "To Payment"),
            ("to_confirm", "To Confirm"),
        ],
    )

    priority = fields.Selection(
        [
            ("0", "Low priority"),
            ("1", "Medium priority"),
            ("2", "High priority"),
            ("3", "Urgent"),
        ],
        default="0",
        tracking=True,
    )

    pick_scheduled_date = fields.Date(
        string="Schedule Shipping Date",
        tracking=True,
        compute="_compute_pick_scheduled_date",
        store=True,
        help="Scheduled date of last modified stock picking",
    )

    planned_shipping_date = fields.Date()

    efarmer_confirm_date = fields.Date(
        string="Confirm Date",
        compute="_compute_efarmer_confirm_date",
        store=True,
        readonly=True,
    )

    missed_partner_data_banner = fields.Html(
        compute="_compute_form_partner_banner", sanitize=False
    )
    missed_fiscal_position_banner = fields.Html(
        compute="_compute_form_partner_banner", sanitize=False
    )
    delivery_term_id = fields.Many2one(
        "delivery.terms",
        string="Delivery Terms",
        domain="[('company_id', '=', company_id)]",
        default=_get_default_delivery_term_id,
    )
    commitment_date = fields.Datetime(
        default=lambda self: datetime.today()
        + relativedelta(days=self._get_default_delivery_term_id().delivery_days)
    )
    tag_ids = fields.Many2many(default=lambda self: self.delivery_term_id.tag_ids)

    def action_to_confirm(self):
        return self.write({"state": "to_confirm"})

    def action_to_payment(self):
        if self.partner_id not in self.message_partner_ids:
            self.message_subscribe([self.partner_id.id])
        return self.write({"state": "to_payment"})

    @api.depends(
        "picking_ids", "picking_ids.scheduled_date", "state", "delivery_status"
    )
    def _compute_pick_scheduled_date(self):
        for order in self:
            if order.state != "sale" or order.delivery_status == "full":
                order.pick_scheduled_date = None
            else:
                active_picks = order.picking_ids.filtered(
                    lambda p: p.state not in ["done", "cancel"]
                )
                order.pick_scheduled_date = (
                    active_picks[0].scheduled_date if active_picks else None
                )

    @api.depends("state")
    def _compute_efarmer_confirm_date(self):
        today = fields.Date().today()
        for order in self:
            if order.state in ("to_confirm", "sale") and not order.efarmer_confirm_date:
                order.efarmer_confirm_date = today

    @api.onchange("delivery_term_id")
    def _onchange_delivery_term_fields(self):
        today = datetime.today()
        for order in self:
            order.commitment_date = today + relativedelta(
                days=order.delivery_term_id.delivery_days
            )
            order.tag_ids = order.delivery_term_id.tag_ids

    @api.depends(
        "partner_id",
        "partner_id.country_id",
        "partner_id.phone",
        "partner_id.email",
        "partner_id.property_account_position_id",
        "fiscal_position_id",
    )
    def _compute_form_partner_banner(self):
        data = [
            (_("Country"), "country_id"),
            (_("Email"), "email"),
            (_("Phone"), "phone"),
        ]
        for rec in self:
            rec.missed_fiscal_position_banner = (
                _(
                    "Please update the Fiscal Position on the Sales Order to match the one on the Contact."
                )
                if rec.fiscal_position_id != rec.partner_id.property_account_position_id
                else ""
            )

            if not rec.partner_id:
                rec.missed_partner_data_banner = ""
                continue
            missed = [
                d[0]
                for d in data
                if not any(bool(getattr(rec.partner_id, r, False)) for r in d[1:])
            ]
            if not missed:
                rec.missed_partner_data_banner = ""
                continue

            rec.missed_partner_data_banner = Markup(
                "%s %s is empty for partner %s. PLEASE UPDATE THE CUSTOMER'S CARD."
            ) % (
                ", ".join(missed),
                _("fields") if len(missed) > 1 else _("field"),
                Markup('<a href="/web#id=%s&model=res.partner&view_type=form">%s</a>')
                % (rec.partner_id.id, rec.partner_id.display_name),
            )

    def _confirmation_error_message(self):
        """METHOD OVERWRITTEN
        Return whether order can be confirmed or not if not then returm error message.
        """
        self.ensure_one()
        if self.state not in {"draft", "sent", "to_confirm"}:
            return _("Some orders are not in a state requiring confirmation.")
        if any(
            not line.display_type and not line.is_downpayment and not line.product_id
            for line in self.order_line
        ):
            return _(
                "Some order lines are missing a product, you need to correct them before going further."
            )

        return False
