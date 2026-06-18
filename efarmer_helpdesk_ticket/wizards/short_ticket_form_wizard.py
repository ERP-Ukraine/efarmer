# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ShortTicketFormWizard(models.TransientModel):
    _name = "short.ticket.form.wizard"
    _description = "Short form for helpdesk ticket"

    ticket_id = fields.Many2one(comodel_name="helpdesk.ticket", string="Ticket")

    choose_product_by = fields.Selection(
        selection=[("serial", "Serial Number"), ("other", "Other")],
        string="Choose Product by:",
    )

    product_id = fields.Many2one(comodel_name="product.product", string="Product")

    product_tracking = fields.Selection(
        related="product_id.tracking", string="Product tracking"
    )

    lot_id = fields.Many2one(
        comodel_name="stock.lot",
        string="Lot/Serial",
    )

    sale_id = fields.Many2one(comodel_name="sale.order", string="Sale order")
    partner_id = fields.Many2one(comodel_name="res.partner", string="Customer")

    email = fields.Char(related="partner_id.email", string="Email")
    phone = fields.Char(related="partner_id.phone", string="Phone")

    efarmer_client_type = fields.Many2one(
        related="partner_id.efarmer_client_type", string="Client Type"
    )

    allowed_tag_ids = fields.Many2many(
        comodel_name="helpdesk.tag",
        relation="short_ticket_form_wizard_allowed_tag_rel",
        string="Allowed Tags",
    )

    tag_ids = fields.Many2many(
        comodel_name="helpdesk.tag",
        relation="short_ticket_form_wizard_tag_rel",
        string="Tags",
    )

    note = fields.Char(string="Note")

    delivery_transfer_id = fields.Many2one(
        comodel_name="stock.picking", string="Delivery Transfer"
    )

    delivery_move_id = fields.Many2one(
        comodel_name="stock.move", string="Delivery Move"
    )

    allowed_lot_ids = fields.Many2many("stock.lot", compute="_compute_allowed_lots")
    allowed_product_ids = fields.Many2many("product.product")
    allowed_move_ids = fields.Many2many("stock.move")
    allowed_transfer_ids = fields.Many2many("stock.picking")
    allowed_sale_ids = fields.Many2many("sale.order")

    @api.depends("choose_product_by")
    def _compute_allowed_lots(self):
        for rec in self:
            if rec.choose_product_by == "serial":
                rec.allowed_lot_ids = self.env["stock.lot"].search([
                    ("product_id.tracking", "=", "serial")
                ])
                rec.allowed_product_ids = self.env["product.product"].search([
                    ("tracking", "=", "serial")
                ])
            else:
                rec.allowed_lot_ids = self.env["stock.lot"].search([
                    ("product_id.tracking", "=", "lot")
                ])
                rec.allowed_product_ids = self.env["product.product"].search([
                    ("tracking", "!=", "serial")
                ])

    @api.onchange("choose_product_by")
    def _onchange_choose_product_by(self):
        self.product_id = False
        self.sale_id = False
        self.lot_id = False
        self.partner_id = False
        self.delivery_move_id = False
        self.delivery_transfer_id = False

    @api.onchange("lot_id")
    def _onchange_lot_id(self):

        if not self.lot_id:
            self.product_id = False
            self.sale_id = False
            self.partner_id = False
            self.delivery_move_id = False
            self.delivery_transfer_id = False
            self._compute_allowed_lots()

        elif self.choose_product_by == "serial":
            self.product_id = self.lot_id.product_id

            move_line_id = (
                self.env["stock.move.line"]
                .search([("lot_id", "=", self.lot_id.id)], order="id desc")
                .filtered(lambda ml: ml.location_dest_id.usage == "customer")[:1]
            )

            self.delivery_move_id = move_line_id.move_id
            self.delivery_transfer_id = self.delivery_move_id.picking_id
            self.sale_id = self.delivery_transfer_id.sale_id
            self.partner_id = self.sale_id.partner_id

        elif self.choose_product_by == "other" and self.lot_id:
            self.product_id = self.lot_id.product_id

            self.allowed_move_ids = (
                self.env["stock.move.line"]
                .search([("lot_id", "=", self.lot_id.id)])
                .filtered(lambda ml: ml.location_dest_id.usage == "customer")
                .mapped("move_id")
            )

            # move_domain = [("id", "in", move_ids.ids)]
            self.allowed_transfer_ids = self.allowed_move_ids.mapped("picking_id")

        elif self.choose_product_by == "other" and not self.lot_id:
            self.allowed_product_ids = self.env["product.product"].search(
                [("tracking", "in", ["lot", "none"])]
            )

    # ---------------------------------------------------------
    # REST OF YOUR FILE (UNCHANGED LOGIC)
    # ---------------------------------------------------------
    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        if self.choose_product_by == "other" and self.partner_id:
            self.allowed_sale_ids = self.env["sale.order"].search(
                [("partner_id", "=", self.partner_id.id)]
            )

    @api.onchange("delivery_transfer_id")
    def _onchange_delivery_transfer_id(self):
        move_domain = []

        if self.choose_product_by == "other" and self.delivery_transfer_id:
            self.sale_id = self.delivery_transfer_id.sale_id
            if self.product_id:
                self.allowed_move_ids = self.delivery_transfer_id.move_ids.filtered(lambda m: m.product_id == self.product_id)

        elif self.choose_product_by == "other" and not self.delivery_transfer_id:
            self.delivery_move_id = False

            search_domain = [("product_id", "=", self.product_id.id)]

            if self.lot_id:
                search_domain.append(("lot_id", "=", self.lot_id.id))

            move_ids = (
                self.env["stock.move.line"]
                .search(search_domain)
                .filtered(lambda ml: ml.location_dest_id.usage == "customer")
                .mapped("move_id")
            )

            move_domain = [("id", "in", move_ids.ids)]
            transfer_ids = move_ids.mapped("picking_id")

            transfer_domain = [("id", "in", transfer_ids.ids)]

            return {
                "domain": {
                    "delivery_transfer_id": transfer_domain,
                    "delivery_move_id": move_domain,
                },
            }

    @api.onchange("product_id")
    def onchange_sale_domain(self):

        if self.choose_product_by == "other" and self.product_id:
            self.sale_id = False
            self.allowed_lot_ids = self.env["stock.lot"].search(
                [("product_id", "=", self.product_id.id)]
            )

    @api.onchange("sale_id")
    def _onchange_sale_id(self):
        if self.choose_product_by == "other" and self.sale_id and not self.partner_id:
            self.partner_id = self.sale_id.partner_id

    def action_run(self):
        name = f""

        if self.product_id.default_code:
            name += f"[{self.product_id.default_code}]"

        name += f" {self.product_id.name} "

        if self.lot_id.name:
            name += f"/ {self.lot_id.name} "

        if self.partner_id:
            name += f"/ {self.partner_id.name}"

        self.ticket_id.write(
            {
                "name": name,
                "sale_order_id": self.sale_id.id,
                "product_id": self.product_id.id,
                "lot_id": self.lot_id.id,
                "partner_id": self.partner_id.id,
                "partner_name": self.partner_id.name,
                "partner_email": self.email,
                "partner_phone": self.phone,
                "delivery_transfer_id": self.delivery_transfer_id.id,
                "delivery_move_id": self.delivery_move_id.id,
                "note": self.note,
                "efarmer_client_type": self.efarmer_client_type.id,
                "tag_ids": [(4, tag) for tag in self.tag_ids.ids],
                "user_id": self.env.uid,
            }
        )

    @api.onchange("email")
    def _onchange_email(self):
        if self.email:
            self.partner_id = self.env["res.partner"].search(
                [("email", "like", self.email)], limit=1
            )
