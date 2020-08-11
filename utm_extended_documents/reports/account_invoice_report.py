from odoo import api, fields, models


class AccountInvoiceReport(models.Model):
    _inherit = 'account.invoice.report'

    source_id = fields.Many2one('utm.source', 'Source', readonly=True)
    medium_id = fields.Many2one('utm.medium', 'Medium', readonly=True)
    campaign_id = fields.Many2one('utm.campaign', 'Campaign', readonly=True)
    utm_term_id = fields.Many2one('utm.term', 'Term', readonly=True)
    utm_content_id = fields.Many2one('utm.content', 'Content', readonly=True)

    @api.model
    def _select(self):
        res = super()._select()
        assert isinstance(res, str)
        return res + '''
            , move.source_id as source_id
            , move.medium_id as medium_id
            , move.campaign_id as campaign_id
            , move.utm_term_id as utm_term_id
            , move.utm_content_id as utm_content_id
        '''

    @api.model
    def _group_by(self):
        res = super()._group_by()
        assert isinstance(res, str)
        return res + (
            ', move.source_id, move.medium_id, move.campaign_id'
            ', move.utm_term_id, move.utm_content_id'
        )
