from odoo import fields, models


class KsefTaxTag(models.Model):
    _name = 'ksef.tax.tag'
    _description = 'KSeF Tax Tag'

    name = fields.Char(required=True)
    description = fields.Char()
