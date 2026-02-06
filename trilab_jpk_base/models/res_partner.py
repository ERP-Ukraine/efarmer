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

    @tools.ormcache('self', 'raise_exception')
    def x_get_eu_vat(self, raise_exception=False):
        self.ensure_one()

        def _error(msg, _error=None):
            if raise_exception:
                raise ValidationError(msg) from _error

        if not self.vat:
            return _error(_('Missing VAT number'))

        vat = re.sub(r'\W', '', self.vat.upper())

        if not re.match(r'^[A-Z]{2}\w', vat):
            # this is VAT w/o country code

            country_id = self.country_id or self.company_id.country_id

            if country_id and country_id in self.env.ref('base.europe').country_ids:
                vat = f'{country_id.code}{vat}'

            else:
                return _error(_('Invalid VAT number (missing country code)'))

        try:
            vat = std_eu_vat.validate(vat)

        except std_eu_vat.ValidationError as error:
            return _error(str(error), error)

        return vat

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

        return None
