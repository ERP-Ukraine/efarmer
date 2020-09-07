from odoo import fields, models


class EfarmerClientType(models.Model):
    _name = 'efarmer.client.type'
    _description = 'Client Type'

    name = fields.Char('Type')
