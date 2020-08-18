from urllib.parse import urlparse, unquote
from odoo import api, fields, models

FIELDS_SEPARATOR = '\n\n'


class TildaWebsite(models.Model):
    _name = 'tilda.website'
    _description = 'Tilda Website'
    _rec_name = 'host'

    host = fields.Char('Host', help='Only requests from this website will be saved.')
    field_ids = fields.One2many('tilda.website.field', 'tilda_website_id', 'Fields Mapping')

    @api.model
    def get_by_referrer(self, referrer):
        if not referrer:
            return False

        url = urlparse(unquote(referrer))
        return self.search([('host', '=', url.netloc)], limit=1)

    def map_tilda_to_odoo_fields(self, kwargs):
        assert isinstance(kwargs, dict)
        res = {}

        for field in self.field_ids:
            value = kwargs.get(field.tilda_field)
            if not value:
                continue

            existed_value = res.get(field.odoo_field_id.name)
            if existed_value:
                value = FIELDS_SEPARATOR.join((existed_value, value))

            res[field.odoo_field_id.name] = value

        return res
