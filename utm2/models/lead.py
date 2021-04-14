from odoo import fields, models


class Lead(models.Model):
    _inherit = 'crm.lead'

    ga = fields.Char('GA UID')
    content_id = fields.Many2one('utm.content', 'Content')
    term_id = fields.Many2one('utm.term', 'Term')
