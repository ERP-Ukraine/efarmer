from odoo import fields, models


class Content(models.Model):
    _name = 'utm.content'
    _description = 'UTM Content'

    _sql_constraints = [
        ('uniq_name', 'unique(name)', "Name must be unique!"),
    ]

    name = fields.Char(required=True)


class Term(models.Model):
    _name = 'utm.term'
    _description = 'UTM Term'

    _sql_constraints = [
        ('uniq_name', 'unique(name)', "Name must be unique!"),
    ]

    name = fields.Char(required=True)
