import re

from stdnum.eu import vat as std_eu_vat
from stdnum.pl import nip as std_pl_nip

from odoo import _, fields, models, tools
from odoo.exceptions import ValidationError


class Partner(models.Model):
    _inherit = 'res.partner'

    x_pl_vat_tp = fields.Boolean(
        string='TP',
        default=False,
        help='Istniejące powiązania między nabywcą a dokonującym dostawy towarów lub usługodawcą, o których mowa '
        'w art. 32 ust. 2 pkt 1 ustawy.',
    )

    @tools.ormcache('self', 'validate', 'check_vies', 'raise_exception')
    def x_get_eu_vat(self, validate=False, check_vies=False, raise_exception=False, vies_timeout=5):
        self.ensure_one()

        country_id = self.country_id or self.company_id.country_id or self.env.company.country_id

        if self.vat and country_id in self.env.ref('base.europe').country_ids:
            # cleanup from all non-word characters
            vat = re.sub(r'\W', '', self.vat.upper())

            if not re.match(r'^[A-Z]{2}\w', vat):
                # this is VAT w/o country code
                vat = f'{country_id.code}{vat}'

            try:
                if validate:
                    vat = std_eu_vat.validate(vat)

                    if check_vies:
                        result = std_eu_vat.check_vies(number=vat, timeout=vies_timeout)

                        if not result or not result.valid:
                            raise ValidationError(_('Invalid VIES state'))

                else:
                    vat = std_eu_vat.compact(vat)

                return vat

            except std_eu_vat.ValidationError as exc:
                if raise_exception:
                    raise ValidationError(str(exc))

    @tools.ormcache('self')
    def x_get_eu_vat_country(self):
        vat = self.x_get_eu_vat()
        return vat and vat[:2]

    @tools.ormcache('self', 'validate', 'raise_exception')
    def x_get_pl_vat(self, validate=True, raise_exception=False):
        self.ensure_one()

        country_id = self.country_id or self.company_id.country_id or self.env.company.country_id

        if country_id.id == self.env['ir.model.data']._xmlid_to_res_id('base.pl') and self.vat:
            try:
                if validate:
                    return std_pl_nip.validate(self.vat)

                else:
                    return std_pl_nip.compact(self.vat)

            except std_pl_nip.ValidationError as exc:
                if raise_exception:
                    raise ValidationError(str(exc))
