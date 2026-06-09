from odoo import fields, models


class AccountAccountTag(models.Model):
    _inherit = 'account.account.tag'

    jpk_document_type = fields.Many2one(comodel_name='jpk.document.type')
    jpk_markup = fields.Char()
    jpk_section = fields.Char()
    jpk_v7_group = fields.Char()
