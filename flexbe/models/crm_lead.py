from odoo import api, fields, models, SUPERUSER_ID


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    from_flexbe = fields.Boolean('From Flexbe', default=False, readonly=True)

    @api.model
    def create_lead_from_flexbe(self, kwargs):
        # Set default values here.
        vals = {
            'contact_name': kwargs.get('data[client][name]', False),
            'phone': kwargs.get('data[client][phone]', False),
            'email_from': kwargs.get('data[client][email]', False),

            'ga': kwargs.get('data[utm][ga_client_id]', False),
            'from_flexbe': True,
        }

        # Make a lead name.
        lead_no = kwargs.get('data[num]', '')
        vals['name'] = 'Flexbe #{}'.format(lead_no)

        # Set a lead type.
        vals['type'] = self.env['ir.config_parameter'].get_param('flexbe.lead.type', 'lead')

        # Save the referrer if it exists.
        referred = kwargs['data[utm][url]']
        if referred:
            vals['referred'] = referred

        # There is a large piece of code below.
        # Actually, it translates the data from form fields into one string.
        # Then it stores the string into `description` field.
        notes = []
        previously_stored_data = vals.values()  # Don't repeat it.

        # data[form_data][111][id] => 111
        data_ids = set([k[15:].split('][')[0][1:] for k in kwargs.keys() if k.startswith('data[form_data]')])

        for data_id in data_ids:
            _value = kwargs.get('data[form_data][{}][value]'.format(data_id))
            if not _value or _value in previously_stored_data:
                continue

            _name = kwargs.get('data[form_data][{}][name]'.format(data_id))
            notes.append('{}:\n{}'.format(_name, _value))

        vals['description'] = '\n\n'.join(notes)

        # Save UTM marks.
        utm = {
            'source': kwargs.get('data[utm][utm_source]'),
            'campaign': kwargs.get('data[utm][utm_campaign]'),
            'medium': kwargs.get('data[utm][utm_medium]'),
            'content': kwargs.get('data[utm][utm_content]'),
            'term': kwargs.get('data[utm][utm_term]'),
        }
        for k, v in utm.items():
            if not v:
                continue

            model = self.env['utm.' + k]
            found = model.search([('name', '=', v)], limit=1)

            field_tech_name = k + '_id'
            if found:
                vals[field_tech_name] = found.id
            elif k == 'campaign':
                record = model.create({'name': v, 'user_id': SUPERUSER_ID})
                vals[field_tech_name] = record.id
            else:
                record = model.create({'name': v})
                vals[field_tech_name] = record.id

        # Create a new lead.
        self.with_context(mail_create_nosubscribe=True).create(vals)
