from odoo import fields, models


class EfarmerClientType(models.Model):
    _name = 'efarmer.client.type'

    name = fields.Char('Type')
