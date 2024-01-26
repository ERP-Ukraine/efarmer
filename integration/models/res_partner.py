# See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _


_region_specific_vat_codes = {
    'xi',
}


class ResPartner(models.Model):
    _name = 'res.partner'
    _inherit = ['res.partner', 'integration.model.mixin']

    location_ids = fields.Many2many(
        'stock.location',
        'res_patner_location_relation',
        'partner_id',
        'location_id',
        string='Customer\'s locations'
    )
    is_address = fields.Boolean(
        string='Is Address',
        default=False,
    )
    integration_id = fields.Many2one(
        string='e-Commerce Integration',
        comodel_name='sale.integration',
        required=False,
        ondelete='set null',
    )
    external_company_name = fields.Char(
        string='External Company Name',
    )

    @api.model
    def _commercial_fields(self):
        return super(ResPartner, self)._commercial_fields() + \
            ['integration_id']

    def _get_contact_name(self, partner, name):
        # Redefined the standart method inside the `name_get` calling in order to add
        # the `external_company_name` char field to PDF report.
        partner_sudo = partner.sudo()
        if partner_sudo.parent_id and partner_sudo.external_company_name:
            return f'{partner_sudo.external_company_name}, {name}'
        return super(ResPartner, self)._get_contact_name(partner, name)

    def _validate_integration_vat(self, vat):
        """
        :return: `is_valid`, `error_message`
        """
        def _vat_error():
            return _(
                'IMPORTANT! The customer "%s" provided VAT number "%s", but it is not a valid '
                'number. Please, make sure to contact the customer to get from him the proper VAT.'
            ) % (self.name, vat)

        if not self.sudo().env.ref('base.module_base_vat').state == 'installed':
            return True, False

        is_valid = self._run_vies_test(vat, self.country_id)
        return is_valid, _vat_error() if not is_valid else False

    @api.model
    def _run_vies_test(self, vat_number, default_country):  # Copied from Odoo-16
        """ Validate a VAT number using the VIES VAT validation. """
        check_result = None

        # First check with country code as prefix of the TIN
        vat_country_code, vat_number_split = self._split_vat(vat_number)
        vat_has_legit_country_code = self.env['res.country'].search([
            ('code', '=', vat_country_code.upper()),
        ])
        if not vat_has_legit_country_code:
            vat_has_legit_country_code = vat_country_code.lower() in _region_specific_vat_codes
        if vat_has_legit_country_code:
            check_result = self.vies_vat_check(vat_country_code, vat_number_split)
            if check_result:
                return vat_country_code

        # If it fails, check with default_country (if it exists)
        if default_country:
            check_result = self.vies_vat_check(default_country.code.lower(), vat_number)
            if check_result:
                return default_country.code.lower()

        return check_result
