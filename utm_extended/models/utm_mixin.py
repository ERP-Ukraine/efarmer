from odoo import fields, models


class UtmMixin(models.AbstractModel):
    _inherit = 'utm.mixin'

    utm_term_id = fields.Many2one('utm.term', 'Term')
    utm_content_id = fields.Many2one('utm.content', 'Content')

    def tracking_fields(self):
        return super().tracking_fields() + [
            ('utm_term', 'utm_term_id', 'odoo_utm_term'),
            ('utm_content', 'utm_content_id', 'odoo_utm_content'),
        ]
