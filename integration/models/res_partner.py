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
    external_customer_ids = fields.Many2many(
        comodel_name='integration.res.partner.external',
        relation='res_partner_external_rel',
        column1='partner_id',
        column2='external_id',
        ondelete='cascade',
        string='External Customer',
        readonly=True,
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

    def _validate_integration_vat(self, vat, country_id):
        """
        :return: `is_valid`, `error_message`
        """

        def _prepare_error_message():
            partner_label = _("partner [%s]", self.name)
            return self._build_vat_error_message(
                country_id and country_id.code.lower() or None, vat, partner_label,
            )

        if not vat:
            return False, False

        if not self.sudo().env.ref('base.module_base_vat').state == 'installed':
            return True, False

        # Split the VAT number and check if it has a legitimate country code
        vat_country_code, vat_number_split = self._split_vat(vat)
        vat_has_legit_country_code = self.env['res.country'].search([
            ('code', '=', vat_country_code.upper()),
        ])

        # Invalid country code
        if not vat_has_legit_country_code:
            return False, _prepare_error_message()

        # Determine the VAT check function
        eu_countries = self.env.ref('base.europe').country_ids
        if country_id in eu_countries:
            check_func = self.vies_vat_check
        else:
            check_func = self.simple_vat_check

        # Validate the VAT number using the determined check function
        is_valid = check_func(vat_country_code, vat_number_split)

        if not is_valid:
            return False, _prepare_error_message()

        return True, False

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

    def _link_external_partner(self, integration: models.Model, external_id: str) -> bool:
        """
        Link an external partner if it exists.
        """
        external_partner = self.env['integration.res.partner.external'].get_external_by_code(
            integration, external_id, raise_error=False,
        )
        if external_partner and external_partner not in self.external_customer_ids:
            self.external_customer_ids = [(4, external_partner.id)]

        return True
