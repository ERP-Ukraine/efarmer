from odoo import fields, models


class JPKGTU(models.Model):

    _name = 'jpk.gtu'
    _description = 'JPK GTU'

    name = fields.Char(required=True, size=100)
    description = fields.Char(size=200)
