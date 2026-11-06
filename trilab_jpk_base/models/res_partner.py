import re

from odoo import _, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import ormcache
from stdnum.eu import vat as std_eu_vat
from stdnum.pl import nip as std_pl_nip

VAT_CLEANUP_RE = re.compile(r'\W')
VAT_COUNTRY_RE = re.compile(r'^[A-Z]{2}\w')
VAT_PREFIX_TO_COUNTRY_CODE = {'EL': 'GR'}
COUNTRY_CODE_TO_VAT_PREFIX = {'GR': 'EL'}


class Partner(models.Model):
    _inherit = 'res.partner'

    x_pl_vat_tp = fields.Boolean(
        'TP',
        help='Istniejące powiązania między nabywcą a dokonującym dostawy towarów lub usługodawcą, o których mowa '
        'w art. 32 ust. 2 pkt 1 ustawy.',
        export_string_translation=False,
    )

    def x_sanitize_vat(self, vat=None):
        if not vat and self:
            self.ensure_one()
            vat = self.vat

        return vat and VAT_CLEANUP_RE.sub('', vat.upper()) or None

    @ormcache('country_code')
    def _x_get_country_id_by_code(self, country_code):
        return self.env['res.country'].search([('code', '=', country_code)], limit=1).id

    def x_get_country_by_code(self, country_code):
        return self.env['res.country'].browse(self._x_get_country_id_by_code(country_code))

    @ormcache('self', 'self.vat', 'self.country_id', 'self.company_id.country_id', 'raise_exception')
    def x_get_eu_vat(self, raise_exception=False):
        self.ensure_one()

        def _error(msg, _error_exc=None):
            if raise_exception:
                raise ValidationError(msg) from _error_exc

            return None

        vat = self.x_sanitize_vat()

        if not vat:
            return _error(_('Missing VAT number'))

        if VAT_COUNTRY_RE.match(vat):
            country_id = self.x_get_country_by_code(VAT_PREFIX_TO_COUNTRY_CODE.get(vat[:2], vat[:2]))

        else:
            country_id = self.country_id or self.company_id.country_id

            if country_id:
                vat = f'{country_id.code}{vat}'

        if country_id not in self.env.ref('base.europe').country_ids:
            return _error(_('Not an EU VAT: %s', vat))

        try:
            vat = std_eu_vat.validate(vat)

        except std_eu_vat.ValidationError as error:
            return _error(str(error), error)

        return COUNTRY_CODE_TO_VAT_PREFIX.get(vat[:2], vat[:2]) + vat[2:]

    @ormcache('self', 'self.vat', 'self.country_id', 'self.company_id.country_id')
    def x_get_eu_vat_country(self):
        vat = self.x_get_eu_vat()

        return vat and vat[:2]

    @ormcache(
        'self',
        'self.vat',
        'self.country_id',
        'self.company_id.country_id',
        'self.env.company.id',
        'validate',
        'raise_exception',
    )
    def x_get_pl_vat(self, validate=True, raise_exception=False):
        self.ensure_one()

        def _error(msg, _error_exc=None):
            if raise_exception:
                raise ValidationError(msg) from _error_exc

            return None

        vat = self.x_sanitize_vat()

        if not vat:
            return _error(_('Missing VAT'))

        country_id = self.country_id or self.company_id.country_id or self.env.company.country_id

        if VAT_COUNTRY_RE.match(vat) and not vat.startswith('PL'):
            return _error(_('Not a PL VAT: %s', vat))

        if not vat.startswith('PL') and country_id.code != 'PL':
            return _error(_('Not a PL VAT: %s', vat))

        try:
            return validate and std_pl_nip.validate(vat) or std_pl_nip.compact(vat)

        except std_pl_nip.ValidationError as error:
            return _error(str(error), error)

    def x_get_jpk_vat_and_country(self):
        self.ensure_one()

        if vat_pl := self.x_get_pl_vat():
            return vat_pl, 'PL'

        if vat_eu := self.x_get_eu_vat():
            return vat_eu[2:], vat_eu[:2]

        country_code = self.country_id.code

        return self.x_sanitize_vat(), COUNTRY_CODE_TO_VAT_PREFIX.get(country_code, country_code) or None
