from odoo import fields, models

FIELDS_SEPARATOR = '\n'


class ExternalWebsiteForm(models.Model):
    _name = 'external.website.form'
    _description = 'External Website Form'
    _rec_name = 'form_uid'

    form_uid = fields.Char('Form ID', required=True)
    referrer = fields.Char('Referrer', required=True)
    field_ids = fields.One2many('external.website.form.field', 'form_id', 'Fields')

    def create_lead(self, vals):
        self.ensure_one()
        assert isinstance(vals, dict)

        creation_values = {'type': 'lead'}
        for field in self.field_ids:
            value = vals.get(field.website_field)
            if not value:
                continue

            existed_value = creation_values.get(field.odoo_field)
            if existed_value:
                value = FIELDS_SEPARATOR.join((existed_value, value))

            creation_values[field.odoo_field] = value

        if 'name' not in creation_values:
            creation_values['name'] = 'unnamed'

        model = self.env['crm.lead'].with_context(mail_create_nosubscribe=True)
        return model.create(creation_values)


class ExternalWebsiteFormField(models.Model):
    _name = 'external.website.form.field'
    _description = 'External Website Form Field'
    _rec_name = 'website_field'

    website_field = fields.Char('Website Name', required=True)
    odoo_field = fields.Char('Odoo Tech Field', required=True)
    form_id = fields.Many2one('external.website.form', 'Form', required=True)
