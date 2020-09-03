import werkzeug
from odoo import fields, models, SUPERUSER_ID

FIELDS_SEPARATOR = '\n'


class ExternalWebsiteForm(models.Model):
    _name = 'external.website.form'
    _description = 'External Website Form'
    _rec_name = 'form_uid'

    form_uid = fields.Char('Form ID', required=True)
    referrer = fields.Char('Referrer', required=True)
    team_id = fields.Many2one('crm.team', 'Sales Team')
    form_tag_ids = fields.Many2many('crm.lead.tag', string='Tags')
    field_ids = fields.One2many('external.website.form.field', 'form_id', 'Field Mapping')
    tag_ids = fields.One2many('external.website.form.tag', 'form_id', 'Tag Mapping')

    def create_lead(self, vals, referrer):
        self.ensure_one()
        assert isinstance(vals, werkzeug.ImmutableOrderedMultiDict)
        assert isinstance(referrer, str)
        model = self.env['crm.lead'].with_context(mail_create_nosubscribe=True)
        creation_values = {'type': 'lead', 'referred': referrer}

        for field in self.field_ids:
            value = vals.get(field.website_field)
            if not value:
                continue

            existed_value = creation_values.get(field.odoo_field_id.name)
            if existed_value:
                value = FIELDS_SEPARATOR.join((existed_value, value))

            creation_values[field.odoo_field_id.name] = value

        tags = self.form_tag_ids
        for tag in self.tag_ids:
            values = [x.strip() for x in vals.getlist(tag.website_field)]
            if tag.website_value in values:
                tags |= tag.tag_id

        for param, field_name, __ in self.env['utm.mixin'].tracking_fields():
            param_value = vals.get(param)
            if param_value:
                param_value = param_value.strip()
                res_model = getattr(model, field_name)

                res_record = res_model.search([('name', '=', param_value)], limit=1)
                if res_record:
                    creation_values[field_name] = res_record.id
                else:
                    param_create_vals = {'name': param_value}
                    # utm.campaign is more complicated than just label
                    # and it has the necessary `user_id` field
                    if field_name == 'campaign_id':
                        param_create_vals['user_id'] = SUPERUSER_ID

                    res_record = res_model.create(param_create_vals)
                    creation_values[field_name] = res_record.id

        if tags:
            creation_values['tag_ids'] = [(6, 0, tags.ids)]

        if 'name' not in creation_values:
            creation_values['name'] = 'A lead from {} form'.format(vals.get('form_id', ''))

        if self.team_id:
            creation_values['team_id'] = self.team_id.id

        return model.create(creation_values)


class ExternalWebsiteFormField(models.Model):
    _name = 'external.website.form.field'
    _description = 'External Website Form Field'
    _rec_name = 'website_field'

    website_field = fields.Char('Website Name', required=True)
    form_id = fields.Many2one('external.website.form', 'Form', required=True)
    odoo_field_id = fields.Many2one(
        comodel_name='ir.model.fields',
        string='Odoo Field',
        required=True,
        domain=[('model_id.model', '=', 'crm.lead')]
    )


class ExternalWebsiteFormTag(models.Model):
    _name = 'external.website.form.tag'
    _description = 'External Website Form Tag'
    _rec_name = 'website_field'

    website_field = fields.Char('Website Name', required=True)
    website_value = fields.Char('Website Value', required=True)
    form_id = fields.Many2one('external.website.form', 'Form', required=True)
    tag_id = fields.Many2one(
        comodel_name='crm.lead.tag',
        string='Tag',
        required=True,
    )
