# See LICENSE file for full copyright and licensing details.

import logging

from odoo import fields, models, api, _

_logger = logging.getLogger(__name__)

try:
    import stdnum
except (ImportError, IOError) as ex:
    _logger.error(ex)


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
        string='E-Commerce Store',
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
        return super(ResPartner, self)._commercial_fields() + ['integration_id']

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
        vat_has_legit_country_code = self.env['res.country'].search_count([
            ('code', '=', vat_country_code.upper())]) > 0

        # Invalid country code
        if not vat_has_legit_country_code:
            return False, _prepare_error_message()

        # Determine the VAT check function
        eu_countries = self.env.ref('base.europe').country_ids
        if country_id in eu_countries:
            is_valid = stdnum.eu.vat.check_vies(vat, timeout=10).valid
        else:
            is_valid = self.simple_vat_check(vat_country_code, vat_number_split)

        if not is_valid:
            return False, _prepare_error_message()

        return True, False

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
