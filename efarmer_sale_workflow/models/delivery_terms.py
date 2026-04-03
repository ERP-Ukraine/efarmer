# Copyright 2023 VentorTech OU
# Part of Ventor modules. See LICENSE file for full copyright and licensing details.
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class DeliveryTerms(models.Model):
    _name = "delivery.terms"
    _description = "Delivery Terms"
    _check_company_auto = True

    name = fields.Char(string="Name", required=True)
    default_for_company = fields.Boolean(string="Default for the Company")
    company_id = fields.Many2one(
        "res.company", "Company", required=True, default=lambda self: self.env.company
    )
    description = fields.Text(string="Description on the Invoice")
    tag_ids = fields.Many2many("crm.tag", string="Tags")
    delivery_days = fields.Integer(string="Delivery Days")

    _sql_constraints = [
        (
            "unique_name_company",
            "UNIQUE(name, company_id)",
            "A delivery term with the same name for the same company already exists.",
        )
    ]

    @api.constrains("default_for_company", "company_id")
    def _check_default_for_company(self):
        for record in self:
            if record.default_for_company:
                other_defaults = self.search(
                    [
                        ("id", "!=", record.id),
                        ("default_for_company", "=", True),
                        ("company_id", "=", record.company_id.id),
                    ]
                )
                if other_defaults:
                    raise ValidationError(
                        "You can only have one delivery term set as default for the same company."
                    )
