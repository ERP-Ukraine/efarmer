from odoo import fields, models


class TildaWebsiteField(models.Model):
    _name = 'tilda.website.field'
    _description = 'Tilda Website Field'

    tilda_field = fields.Char('Tilda Field', required=True)
    odoo_field_id = fields.Many2one(
        comodel_name='ir.model.fields',
        string='Odoo Field',
        required=True,
        domain=[('model_id.model', '=', 'crm.lead')]
    )
    tilda_website_id = fields.Many2one('tilda.website', 'Tilda Website', required=True)

    def name_get(self):
        return [(each.id, each.tilda_field + ' / ' + each.odoo_field_id.name)
                for each in self]
