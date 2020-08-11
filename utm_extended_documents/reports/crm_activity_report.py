from odoo import fields, models


class CrmActivityReport(models.Model):
    _inherit = 'crm.activity.report'

    source_id = fields.Many2one('utm.source', 'Source', readonly=True)
    medium_id = fields.Many2one('utm.medium', 'Medium', readonly=True)
    campaign_id = fields.Many2one('utm.campaign', 'Campaign', readonly=True)
    utm_term_id = fields.Many2one('utm.term', 'Term', readonly=True)
    utm_content_id = fields.Many2one('utm.content', 'Content', readonly=True)

    def _select(self):
        res = super()._select()
        assert isinstance(res, str)
        return res + '''
            , l.source_id as source_id
            , l.medium_id as medium_id
            , l.campaign_id as campaign_id
            , l.utm_term_id as utm_term_id
            , l.utm_content_id as utm_content_id
        '''
