# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import fields, models, api


class ProductVat(models.Model):
    _name = 'product.vat'
    _description = "Product Vat"

    name = fields.Char('Name', required=True)
    description_on_docs = fields.Html('Description on Documents')
