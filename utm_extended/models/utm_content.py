from odoo import fields, models


class UtmContent(models.Model):
    _name = 'utm.content'
    _description = 'UTM Content'

    name = fields.Char(string='Content Name', required=True, translate=True)
