from odoo import fields, models


class UtmTerm(models.Model):
    _name = 'utm.term'
    _description = 'UTM Term'

    name = fields.Char(string='Term Name', required=True, translate=True)
