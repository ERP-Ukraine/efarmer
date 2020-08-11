from odoo import fields, models


class SaleReport(models.Model):
    _inherit = 'sale.report'

    utm_term_id = fields.Many2one('utm.term', 'Term', readonly=True)
    utm_content_id = fields.Many2one('utm.content', 'Content', readonly=True)

    def _query(self, with_clause='', fields={}, groupby='', from_clause=''):
        fields.update({
            'utm_term_id': ', s.utm_term_id as utm_term_id',
            'utm_content_id': ', s.utm_content_id as utm_content_id',
        })
        groupby += ', s.utm_term_id, s.utm_content_id'
        return super()._query(with_clause, fields, groupby, from_clause)
