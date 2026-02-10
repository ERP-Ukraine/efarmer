# Copyright 2026 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import api, fields, models


class ProductVat(models.Model):
    _name = "product.vat"
    _description = "Product Vat"

    name = fields.Char("Name", required=True)
    description_on_docs = fields.Html("Description on Documents")
