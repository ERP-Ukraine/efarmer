from odoo import fields, models


class JpkAccountTag(models.Model):
    _name = 'jpk.account.tag'
    _description = 'JPK Account Tag'

    account_tag_id = fields.Many2one(comodel_name='account.account.tag')
    jpk_document_type = fields.Many2one(comodel_name='jpk.document.type')
    jpk_markup = fields.Char()
    jpk_section = fields.Char()
    jpk_v7_group = fields.Char()
