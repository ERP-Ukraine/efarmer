from odoo import _, api, fields, models


class CheckPartnerGusDetail(models.TransientModel):
    _name = 'trilab.check.partner.gus'
    _description = 'Trilab Check GUS Partner'

    partner_id = fields.Many2one('res.partner')
    details_id = fields.Many2one('trilab.check.partner.details')

    name = fields.Char(string='Name')
    street = fields.Char(string='Street')
    street2 = fields.Char(string='Street2')
    city = fields.Char(string='City')
    state_id = fields.Many2one('res.country.state', string='State')
    zip = fields.Char(string='Zip')
    country_id = fields.Many2one('res.country', string='Country')
    phone = fields.Char(string='Phone')
    email = fields.Char(string='Email')
    website = fields.Char(string='Website')
    regon = fields.Char(string='REGON')
    krs = fields.Char(string='KRS')
    x_pl_gus_update_date = fields.Date(string='GUS Update Date')
    vat = fields.Char(string='VAT')
    lang = fields.Char(string='Language')
    x_pl_business_type = fields.Char(string='Business Type')
    x_pl_gus_inactive_date = fields.Date(string='GUS Business Inactive Date')


class CheckPartnerDetails(models.TransientModel):
    _name = 'trilab.check.partner.details'
    _description = 'Trilab Check Partner Details Wizard'

    check_id = fields.Many2one('trilab.check.partner')

    gus_selected_id = fields.Many2one('trilab.check.partner.gus', domain="[('details_id', '=', id)]")
    gus_selection_ids = fields.One2many('trilab.check.partner.gus', 'details_id')

    partner_id = fields.Many2one('res.partner')

    name = fields.Char(string='Name', related='partner_id.name')
    vat = fields.Char(string='VAT', related='partner_id.vat')

    x_name = fields.Char(related='gus_selected_id.name', string='New Name')
    x_vat = fields.Char(related='gus_selected_id.vat', string='New VAT')

    street = fields.Char(string='Street', related='partner_id.street')
    street2 = fields.Char(string='Street2', related='partner_id.street2')
    zip = fields.Char(string='Zip', related='partner_id.zip')
    city = fields.Char(string='City', related='partner_id.city')
    state_id = fields.Many2one('res.country.state', string='State', related='partner_id.state_id')
    phone = fields.Char(string='Phone', related='partner_id.phone')
    email = fields.Char(string='Email', related='partner_id.email')

    x_street = fields.Char(related='gus_selected_id.street', string='New Street')
    x_street2 = fields.Char(related='gus_selected_id.street2', string='New Street2')
    x_zip = fields.Char(related='gus_selected_id.zip', string='New Zip')
    x_city = fields.Char(related='gus_selected_id.city', string='New City')
    x_state_id = fields.Many2one('res.country.state', related='gus_selected_id.state_id', string='New State')
    x_phone = fields.Char(related='gus_selected_id.phone', string='New Phone')
    x_email = fields.Char(related='gus_selected_id.email', string='New Email')

    regon = fields.Char(string='REGON', related='partner_id.regon')
    krs = fields.Char(string='KRS/Reg. No', related='partner_id.krs')

    x_regon = fields.Char(related='gus_selected_id.regon', string='New REGON')
    x_krs = fields.Char(related='gus_selected_id.krs', string='New KRS')

    x_pl_gus_update_date = fields.Date(related='partner_id.x_pl_gus_update_date', string='Update Date')

    user_id = fields.Many2one('res.users', related='partner_id.user_id')
    category_id = fields.Many2many('res.partner.category', related='partner_id.category_id')
    company_id = fields.Many2one('res.company', related='partner_id.company_id')
    is_company = fields.Boolean(related='partner_id.is_company')
    parent_id = fields.Many2one('res.partner', related='partner_id.parent_id')
    active = fields.Boolean(related='partner_id.active')

    x_pl_nip_state = fields.Char(related='partner_id.x_pl_nip_state')
    x_pl_nip_check_date = fields.Date(related='partner_id.x_pl_nip_check_date')

    x_pl_vies_state = fields.Selection(related='partner_id.x_pl_vies_state')
    x_pl_vies_check_date = fields.Date(related='partner_id.x_pl_vies_check_date')

    x_pl_gus_inactive_date = fields.Date(
        related='partner_id.x_pl_gus_inactive_date', string='GUS Business Inactive Date'
    )
    x_x_pl_gus_inactive_date = fields.Date(
        related='gus_selected_id.x_pl_gus_inactive_date', string='New GUS Business Inactive Date'
    )

    is_error = fields.Boolean(compute='compute_is_error')
    is_warning = fields.Boolean(compute='compute_is_error')
    error_type = fields.Char()
    error_message = fields.Char()
    is_multi_mode = fields.Boolean(compute='_compute_is_multi_mode')

    def _compute_is_multi_mode(self):
        for rec_id in self:
            rec_id.is_multi_mode = len(self.check_id.check_ids) > 1

    @api.depends('error_type', 'gus_selected_id')
    def compute_is_error(self):
        for rec_id in self:
            rec_id.is_error = rec_id.is_warning = False

            if rec_id.error_type and rec_id.error_type != 'vies_ok':
                if rec_id.error_type == 'gus_multiple':
                    rec_id.is_warning = not rec_id.gus_selected_id

                elif rec_id.error_type != 'gus_update':
                    rec_id.is_error = True

        self.flush_recordset()

    def get_update_data(self):
        keys = [
            'name',
            'street',
            'street2',
            'city',
            'zip',
            'phone',
            'email',
            'website',
            'regon',
            'krs',
            'x_pl_gus_update_date',
            'vat',
            'lang',
            'x_pl_gus_inactive_date',
        ]

        data = {key: getattr(self.gus_selected_id, key) for key in keys}
        data['state_id'] = self.gus_selected_id.state_id.id if self.gus_selected_id.state_id else None
        data['country_id'] = self.gus_selected_id.country_id.id if self.gus_selected_id.country_id else None

        # no override if key is True
        for key in ['email', 'phone', 'website']:
            if getattr(self.partner_id, key):
                data.pop(key, None)

        return data

    def update_partner(self):
        if self.partner_id and self.gus_selected_id:
            self.error_type = None
            self.x_pl_gus_update_date = fields.Date.today()
            self.partner_id.write(self.get_update_data())
            self.partner_id.message_post(body=_('Partner data updated from GUS.'))
            self.partner_id.flush_recordset()

    # noinspection PyMethodMayBeStatic
    def close_popup(self):
        return {}

    def back_to_wizard(self):
        # to prevent wizard from closing, return the same wizard
        return self.partner_id._x_pl_check_action(record_id=self.check_id.id, title=_('Updated data from GUS'))


class CheckPartner(models.TransientModel):
    _name = 'trilab.check.partner'
    _description = 'Trilab Check Partner Wizard'

    check_ids = fields.One2many('trilab.check.partner.details', inverse_name='check_id')
    mode = fields.Selection([('gus', 'GUS'), ('nip', 'NIP'), ('vies', 'VIES')])
    errors_count = fields.Integer(compute='_compute_errors_count', store=False)

    @api.depends('check_ids', 'check_ids.error_type')
    def _compute_errors_count(self):
        for check_id in self:
            check_id.errors_count = len(check_id.check_ids.filtered(lambda rec_id: rec_id.error_type))

    def update_selected_partners(self):
        for check_id in self.check_ids.filtered(
            lambda rec_id: rec_id.error_type in ('gus_multiple', 'gus_update') and rec_id.gus_selected_id
        ):
            check_id.update_partner()
