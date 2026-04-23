import json
import re
from datetime import datetime
from types import SimpleNamespace
from typing import Optional

import requests
import zeep
import zeep.exceptions
from odoo import _, _lt, api, fields, models, tools
from odoo.exceptions import UserError, ValidationError
from stdnum.eu import vat as std_eu_vat
from stdnum.pl import nip as std_pl_nip
from stdnum.pl import pesel as std_pl_pesel

from .gus_regon import EntityType, GusClient, GusException, ReportType

MF_GOV_PL_WSDL = 'https://sprawdz-status-vat.mf.gov.pl/?wsdl'

KRD_ENV = {
    'prod': 'https://services.krd.pl/Chase/3.1/Search.svc?WSDL',
    'test': 'https://demo.krd.pl/Chase/3.1/Search.svc?WSDL',
}

VIES_ERRORS = {
    'INVALID_INPUT': _lt('The provided CountryCode is invalid or the VAT number is empty.'),
    'GLOBAL_MAX_CONCURRENT_REQ': _lt(
        'Your Request for VAT validation has not been processed. The maximum number of concurrent requests '
        'has been reached.'
    ),
    'SERVICE_UNAVAILABLE': _lt('An error was encountered either at the network level or the Web application level.'),
    'MS_UNAVAILABLE': _lt('The application at the Member State is not replying or not available.'),
    'TIMEOUT': _lt('The application did not receive a reply within the allocated time period.'),
    'MS_MAX_CONCURRENT_REQ': _lt(
        'Your request cannot be processed due to high traffic towards the Member State you are trying to reach. '
        'Please try again later.'
    ),
}

GUS_REGON_FIELD_MAP = {
    'name': 'nazwa',
    'street': 'adSiedzUlica_Nazwa',
    'street_number': 'adSiedzNumerNieruchomosci',
    'unit_number': 'adSiedzNumerLokalu',
    'street2': 'adSiedzNietypoweMiejsceLokalizacji',
    'state_id': 'adSiedzWojewodztwo_Nazwa',
    'zip': 'adSiedzKodPocztowy',
    'phone': 'numerTelefonu',
    'phone_internal': 'numerWewnetrznyTelefonu',
    'email': 'adresEmail',
    'website': 'adresStronyinternetowej',
    'krs': 'numerWRejestrzeEwidencji',
    'city': 'adSiedzMiejscowosc_Nazwa',
    'x_pl_gus_inactive_date': 'dataZakonczeniaDzialalnosci',
}

GUS_REGON_PREFIX_MAP = {
    EntityType.OsFizyczna: 'fiz_{}',
    EntityType.OsPrawna: 'praw_{}',
    EntityType.JednostkaLokalnaOsFizycznej: 'lokfiz_{}',
    EntityType.JednostkaLokalnaOsPrawnej: 'lokpraw_{}',
}

MF_WL_PROD_URL = 'https://wl-api.mf.gov.pl/'

MF_WL_BATCH_SIZE = 30

GUS_SILO_MAP = {
    '1': ReportType.OsFizycznaDzialalnoscCeidg,
    '2': ReportType.OsFizycznaDzialalnoscRolnicza,
    '3': ReportType.OsFizycznaDzialalnoscPozostala,
    '4': ReportType.OsFizycznaDzialalnoscSkreslona,
}

X_PL_NIP_STATE = {
    'N': 'Podmiot o podanym identyfikatorze podatkowym NIP nie jest zarejestrowany jako podatnik VAT',
    'C': 'Podmiot o podanym identyfikatorze podatkowym NIP jest zarejestrowany jako podatnik VAT czynny',
    'Z': 'Podmiot o podanym identyfikatorze podatkowym NIP jest zarejestrowany jako podatnik VAT zwolniony',
    'I': 'Błąd zapytania - Nieprawidłowy Numer Identyfikacji Podatkowej',
    'D': 'Błąd zapytania - Data spoza ustalonego zakresu',
    'X': 'Usługa nieaktywna',
}

X_PL_NIP_STATE_HELP = 'Status odpowiada poniższej liście:\n' + '\n'.join(
    f'{_k} - {_v}' for _k, _v in X_PL_NIP_STATE.items()
)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    x_pl_nip_state = fields.Char(string='VAT Status', tracking=True, help=X_PL_NIP_STATE_HELP)

    x_pl_vies_state = fields.Selection(
        [('valid', 'Valid'), ('invalid', 'Invalid'), ('no_info', 'No information')],
        string='VIES Status',
        default='no_info',
    )

    x_pl_nip_check_date = fields.Date(string='VAT Check Date')
    x_pl_gus_update_date = fields.Date(string='GUS Update Date')
    x_pl_vies_check_date = fields.Date(string='VIES Check Date')

    x_pl_business_type = fields.Selection(
        selection=[
            (EntityType.OsFizyczna.value, 'Osoba fizyczna'),
            (EntityType.OsPrawna.value, 'Osoba prawna'),
            (EntityType.JednostkaLokalnaOsFizycznej.value, 'Jednostka lokalna osoby fizycznej'),
            (EntityType.JednostkaLokalnaOsPrawnej.value, 'Jednostka lokalna osoby prawnej'),
        ],
        string='Business Type',
    )

    regon = fields.Char(string='REGON')
    krs = fields.Char(string='KRS/NR Ew.')
    pesel = fields.Char(string='PESEL')

    x_pl_is_poland = fields.Boolean(compute='x_compute_country_flag', store=False)
    x_pl_is_europe = fields.Boolean(compute='x_compute_country_flag', store=False)

    x_pl_enable_gus = fields.Boolean(compute='x_compute_enable_gus_krd', store=False)
    x_pl_enable_krd = fields.Boolean(compute='x_compute_enable_gus_krd', store=False)

    x_pl_gus_inactive_date = fields.Date(string='GUS Business Inactive Date', copy=False, readonly=True)

    @api.constrains('vat')
    def _x_check_vat_duplicate(self):
        if self.env.company.x_pl_validate_vat:
            to_validate = tuple(
                re.sub(r'\D', '', partner_id.vat) for partner_id in self if partner_id.vat and not partner_id.parent_id
            )

            if not self.env.user.has_group('trilab_pl_partners_sync.group_allow_duplicate_vat') and to_validate:
                query = """SELECT REGEXP_REPLACE(vat, '\\D', '', 'g'), COUNT(*) 
                              FROM res_partner 
                              WHERE REGEXP_REPLACE(vat, '\\D', '', 'g') IN %s
                                AND parent_id IS NULL
                              GROUP BY 1 
                              HAVING count(*) > 1"""
                self._cr.execute(query, (to_validate,))

                if self._cr.fetchone():
                    raise ValidationError(_('This VAT is already assigned to another partner'))

                if hasattr(self, 'check_vat'):
                    return self.check_vat()

        return None

    def x_pl_check_vies_cron(self):
        partner_ids = self.search(
            [
                ('is_company', '=', True),
                ('country_id', 'in', (self.env.ref('base.europe').country_ids - self.env.ref('base.pl')).ids),
                ('vat', '!=', False),
                ('user_id', '!=', False),
            ]
        )

        for connected_user_id in partner_ids.user_id:
            for partner_id in partner_ids.filtered(lambda p_id: p_id.user_id == connected_user_id):
                partner_id = partner_id.with_context({'lang': partner_id.lang})
                try:
                    partner_id.x_pl_check_vies()
                except ValidationError as error:
                    partner_id.message_post(
                        body=_('Error while checking VIES: %s', str(error.args[0])),
                        partner_ids=connected_user_id.partner_id.ids,
                    )

    @api.depends('country_id')
    def x_compute_country_flag(self):
        country_pl_id = self.env.ref('base.pl')
        country_eu_ids = self.env.ref('base.europe').country_ids
        for partner_id in self:
            country_id = partner_id.country_id or self.env.company.country_id
            partner_id.x_pl_is_poland = country_id == country_pl_id
            partner_id.x_pl_is_europe = partner_id.x_pl_is_poland or country_id in country_eu_ids

    @api.depends('company_id')
    def x_compute_enable_gus_krd(self):
        for partner_id in self:
            company_id = partner_id.company_id or self.env.company
            partner_id.x_pl_enable_gus = company_id.x_pl_enable_gus
            partner_id.x_pl_enable_krd = company_id.x_pl_enable_krd

    @tools.ormcache('self', 'raise_exception')
    def x_pl_get_eu_vat(self, raise_exception=False):
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

    def x_pl_check_vies(self, raise_exception=True, post_change=True):
        result = {}

        has_vies_valid_field = 'vies_valid' in self._fields
        response = None
        for partner_id in self:
            id_response = None

            try:
                vat = partner_id.x_pl_get_eu_vat(raise_exception=True)
                company_vat = (partner_id.company_id or self.env.company).partner_id.x_pl_get_eu_vat()
                response = std_eu_vat.check_vies_approx(vat, company_vat)
                id_response = response['requestIdentifier']
                result[partner_id.id] = {'error_type': 'vies_ok', 'response_id': id_response}

            except (std_eu_vat.ValidationError, zeep.exceptions.Fault) as error:
                if str(error) in VIES_ERRORS:
                    error = VIES_ERRORS[str(error)]
                else:
                    error = str(error)

                if raise_exception:
                    raise ValidationError(error) from error

                else:
                    result[partner_id.id] = {
                        'error_type': 'vies_error',
                        'error_message': error,
                        'response_id': id_response,
                    }

            if response and response['valid']:
                partner_id.x_pl_vies_state = 'valid'
                message = _('Valid VIES')

            else:
                partner_id.x_pl_vies_state = 'invalid'
                message = _('Invalid VIES')

                if not response and (error := result.get(partner_id.id, {}).get('error_message')):
                    message += f': {error}'

            partner_id.x_pl_vies_check_date = fields.Date.today()

            if has_vies_valid_field:
                partner_id.vies_valid = partner_id.x_pl_vies_state == 'valid'

            if id_response:
                message += _(', id: %s', id_response)

            if post_change:
                partner_id.message_post(body=message)

        return result

    @api.constrains('pesel')
    def x_constrains_pesel(self):
        for partner_id in self.filtered('pesel'):
            try:
                std_pl_pesel.validate(partner_id.pesel)
            except std_pl_pesel.ValidationError as error:
                raise ValidationError(str(error)) from error

    def _x_parse_gus_data(self, data: dict, company_type: EntityType, for_model=False):
        poland_id = self.env.ref('base.pl')

        fields_map = {key: GUS_REGON_PREFIX_MAP[company_type].format(val) for key, val in GUS_REGON_FIELD_MAP.items()}

        company_data = SimpleNamespace(**{mt: data.get(mf) for mt, mf in fields_map.items()})

        # mapping exception
        if company_type == EntityType.OsFizyczna:
            fields_map['krs'] = f'fizC_{GUS_REGON_FIELD_MAP["krs"]}'

        # data cleanup
        if company_data.zip and '-' not in company_data.zip:
            company_data.zip = f'{company_data.zip[:2]}-{company_data.zip[2:]}'

        if company_data.unit_number:
            if company_data.street_number:
                company_data.street_number = f'{company_data.street_number}/{company_data.unit_number}'
            else:
                company_data.street_number = company_data.unit_number

            company_data.unit_number = None

        if not company_data.street:
            if company_data.city:
                company_data.street = company_data.city
                post_city = data.get(GUS_REGON_PREFIX_MAP[company_type].format('adSiedzMiejscowoscPoczty_Nazwa'))
                if post_city:
                    company_data.city = post_city
            else:
                company_data.street = ''

        if company_data.street_number:
            company_data.street = f'{company_data.street} {company_data.street_number}'
            company_data.street_number = None

        if company_data.phone_internal:
            company_data.phone = _('%s i. %s', company_data.phone, company_data.phone_internal)
            company_data.phone_internal = None

        # noinspection PyProtectedMember
        if company_data.state_id and isinstance(company_data.state_id, str):
            state_id = poland_id.state_ids.search([('name', '=', company_data.state_id.lower())], limit=1)
            if state_id:
                company_data.state_id = state_id.id if for_model else {'id': state_id.id, 'name': state_id.name}
            else:
                company_data.state_id = None

        output_dict = {
            'x_pl_gus_update_date': fields.Date.today(),
            'x_pl_business_type': company_type.value,
            'lang': self.env['res.lang'].search([('iso_code', 'ilike', poland_id.code)], limit=1).code,
        }

        if for_model:
            output_dict['country_id'] = poland_id.id
        else:
            output_dict['country_id'] = {'id': poland_id.id, 'display_name': poland_id.display_name}

        for field in fields_map.keys():
            if value := getattr(company_data, field):
                output_dict[field] = value

        # parse & validate date
        if 'x_pl_gus_inactive_date' in output_dict:
            try:
                output_dict['x_pl_gus_inactive_date'] = fields.Date.to_string(
                    datetime.strptime(output_dict['x_pl_gus_inactive_date'], '%Y-%m-%d')
                )
            except (ValueError, TypeError):
                del output_dict['x_pl_gus_inactive_date']

        return output_dict

    @staticmethod
    def x_sanitize_nip(nip):
        if nip:
            return re.sub(r'\D', '', nip)
        return nip

    @staticmethod
    def _x_get_gus_report_type(company_type: EntityType, silos_id: str):
        report = None

        if company_type == EntityType.OsFizyczna:
            report = GUS_SILO_MAP.get(silos_id)

        elif company_type == EntityType.JednostkaLokalnaOsFizycznej and silos_id in ('1', '2', '3'):
            report = ReportType.JednLokalnaOsFizycznej

        elif company_type == EntityType.OsPrawna and silos_id == '6':
            report = ReportType.OsPrawna

        elif company_type == EntityType.JednostkaLokalnaOsPrawnej and silos_id == '6':
            report = ReportType.JednLokalnaOsPrawnej

        return report

    @staticmethod
    def _x_add_fiz_key_to_gus_report_if_ceidg(report, response):
        if report == ReportType.OsFizycznaDzialalnoscCeidg:
            for key in GUS_REGON_FIELD_MAP.values():
                ceidg_key = f'fizC_{key}'
                if ceidg_key in response:
                    response[f'fiz_{key}'] = response[ceidg_key]
        return response

    def _x_pl_get_gus_data(self, nip=None, for_model=False, raise_exception=False, timeout=300):
        self.x_pl_validate_vat(nip, raise_exception)

        api_key = self.env['ir.config_parameter'].sudo().get_param('trilab_gusregon.x_pl_gus_api_key')

        companies_data = []

        if not self.env.company.x_pl_enable_gus:
            return companies_data

        if not api_key:
            raise ValidationError(_('Please set GUS API key in General Settings'))

        gus = GusClient(api_key=api_key, timeout=timeout)

        try:
            response = gus.get_partners_data(nip=self.x_sanitize_nip(nip))
        except GusException as error:
            raise ValidationError(_('Invalid data for VAT (%s)', str(error))) from error

        if not response:
            return companies_data

        if isinstance(response, dict):
            response = [response]

        for company in response:
            company_type = EntityType(company.get('Typ'))
            silos_id = company.get('SilosID', '0')
            report = self._x_get_gus_report_type(company_type, silos_id)

            if not report:
                raise ValidationError(_('invalid combination of Type(%s) and SilosID(%s)', company_type, silos_id))

            regon = company.get('Regon')
            response = gus.get_full_report(regon, report, raise_exception=False)
            response = self._x_add_fiz_key_to_gus_report_if_ceidg(report, response)

            output_dict = self._x_parse_gus_data(response, company_type, for_model=for_model)

            output_dict['regon'] = regon
            output_dict['vat'] = nip or company.get('Nip')

            companies_data.append(output_dict)

        return companies_data

    def x_pl_update_gus_data(self):
        errors = {}

        for partner_id in self:
            if partner_id.country_id != self.env.ref('base.pl'):
                raise ValidationError(_('Customer must be from Poland'))

            if not partner_id.vat:
                raise ValidationError(_('VAT is required'))

            # noinspection PyProtectedMember
            output = partner_id._x_pl_get_gus_data(nip=partner_id.vat, for_model=True)

            if output:
                errors[partner_id.id] = {
                    'error_type': 'gus_multiple' if len(output) > 1 else 'gus_update',
                    'error_message': (
                        _('Multiple records found in GUS please select correct one.')
                        if len(output) > 1
                        else _('Data successfully fetched from GUS')
                    ),
                    'records': output,
                }
            else:
                errors[partner_id.id] = {'error_type': 'gus_invalid_vat', 'error_message': _('VAT is not valid')}

        return errors

    def x_pl_check_mf_nip(self, raise_exception=True, post_change=False):
        if self.env['ir.config_parameter'].sudo().get_param('trilab_mf_check_method', 'ws') == 'ws':
            return self.x_pl_check_mf_nip_ws(raise_exception=raise_exception, post_change=post_change)

        else:
            return self.x_pl_check_mf_nip_wl(raise_exception=raise_exception, post_change=post_change)

    def x_pl_check_mf_nip_ws(self, raise_exception=True, post_change=False):
        poland_id = self.env.ref('base.pl')
        errors = {}

        for partner_id in self:
            # noinspection PyBroadException
            try:
                if partner_id.country_id != poland_id or not partner_id.vat:
                    raise ValidationError('not .pl')

                client = zeep.Client(MF_GOV_PL_WSDL)
                response = client.service.SprawdzNIP(ResPartner.x_pl_validate_vat(partner_id.vat, raise_exception=True))
                partner_id.x_pl_nip_state = response['Kod']
                partner_id.x_pl_nip_check_date = fields.Date.today()

                if post_change:
                    partner_id.message_post(
                        body=_(
                            'Ministry of Finance VAT Validity checked (%(code)s: %(description)s)',
                            code=partner_id.x_pl_nip_state,
                            description=X_PL_NIP_STATE.get(partner_id.x_pl_nip_state, _('Unknown')),
                        )
                    )

            except ValidationError:
                if raise_exception:
                    raise
                else:
                    errors[partner_id.id] = {'error_type': 'invalid_nip', 'error_message': _('Invalid VAT number')}

            except std_pl_nip.ValidationError as error:
                if raise_exception:
                    raise ValidationError(str(error)) from error

                else:
                    errors[partner_id.id] = {'error_type': 'invalid_nip', 'error_message': str(e)}

            except zeep.exceptions.Error as error:
                if raise_exception:
                    raise

                else:
                    partner_id.x_pl_nip_state = False
                    partner_id.x_pl_nip_check_date = False

                    errors[partner_id.id] = {'error_type': 'invalid_nip', 'error_message': str(error)}

        return errors

    def x_pl_check_mf_nip_wl(self, raise_exception=True, post_change=False):
        # use whitelist APIs
        poland_id = self.env.ref('base.pl')
        today = fields.Date.today()
        errors = {}

        # take only PL companies with VAT
        partner_ids = self.filtered(lambda p_id: p_id.vat and p_id.country_id == poland_id)

        # process data in batches, API limitation
        for chunk_index in range(0, len(partner_ids), MF_WL_BATCH_SIZE):
            batch = {}
            batch_error = None

            # first validation, check if VAT is valid, to avoid unnecessary check for invalid NIP numbers
            for partner_id in partner_ids[chunk_index : chunk_index + MF_WL_BATCH_SIZE]:
                vat = self.x_pl_validate_vat(partner_id.vat)

                if vat:
                    batch[vat] = partner_id

                else:
                    if raise_exception:
                        raise ValidationError(
                            _('Invalid VAT number %(vat)s for %(partner)s', vat=partner_id.vat, partner=partner_id.name)
                        )

                    errors[partner_id.id] = {'error_type': 'invalid_nip', 'error_message': _('Invalid VAT number')}

            # second validation with Ministry of Finance
            try:
                response = requests.get(
                    f'{MF_WL_PROD_URL}api/search/nips/{",".join(batch.keys())}', params={'date': today.isoformat()}
                )

                response.raise_for_status()
                response_json = response.json()

                for status in response_json.get('result', {}).get('entries', []):
                    partner_id = batch.pop(status.get('identifier'))

                    partner_id.x_pl_nip_check_date = today

                    try:
                        subject = status['subjects'][0]
                        # get only first letter: Czynny -> C, Zwolniony -> Z, Niezarejestrowany -> N
                        partner_id.x_pl_nip_state = subject['statusVat'][0]

                    except (KeyError, IndexError):
                        partner_id.x_pl_nip_state = 'I'

                    if post_change:
                        partner_id.message_post(
                            body=_(
                                'Ministry of Finance VAT Validity checked (%(code)s: %(description)s, id: %(rid)s)',
                                code=partner_id.x_pl_nip_state,
                                description=X_PL_NIP_STATE.get(partner_id.x_pl_nip_state, _('Unknown')),
                                rid=response_json.get('result', {}).get('requestId', '-'),
                            )
                        )

            except (requests.exceptions.RequestException, ValidationError, json.JSONDecodeError) as error:
                if raise_exception:
                    raise UserError(str(error)) from error

                batch_error = {'error_type': 'invalid_mf_api', 'error_message': _('Error from API: %s', str(error))}

            if batch_error:
                for partner_id in batch.values():
                    errors[partner_id.id] = batch_error

            # for those remaining partners, we did not get data from MF
            for partner_id in batch.values():
                errors[partner_id.id] = {'error_type': 'invalid_mf_api', 'error_message': _('No data from MF API')}

        return errors

    def x_pl_check_krd(self):
        self.ensure_one()

        company_id = self.env.company
        if not company_id.x_pl_krd_login or not company_id.x_pl_krd_pass:
            raise ValidationError(_('Please set KRD login and password in company settings'))

        if not self.country_id or self.country_id.code != 'PL':
            raise ValidationError(_('The company/customer must be registered in Poland'))

        if self.is_company and not self.vat:
            raise ValidationError(_('VAT is required'))

        if not self.is_company and not self.pesel:
            raise ValidationError(_('PESEL is required'))

        client = zeep.Client(KRD_ENV[company_id.x_pl_krd_env])

        auth_header = {
            'Authorization': {
                'AuthorizationType': ['LoginAndPassword'],
                'Login': company_id.x_pl_krd_login,
                'Password': company_id.x_pl_krd_pass,
            }
        }

        if self.is_company:
            response = client.service.SearchNonConsumer(Number=self.vat, NumberType='TaxId', _soapheaders=auth_header)

        else:
            response = client.service.SearchConsumer(
                NumberType='Pesel',
                Number=self.pesel,
                AuthorizationDate=fields.Datetime.now().isoformat(),
                _soapheaders=auth_header,
            )

        response = {
            'Summary': response['body']['DisclosureReport']['Summary'],
            'PositiveInformationSummary': response['body']['DisclosureReport']['PositiveInformationSummary'],
        }

        # noinspection PyProtectedMember
        self.message_post(body=self.env['ir.qweb']._render('trilab_pl_partners_sync.krd_result', response))

    @api.model
    @tools.ormcache('query')
    def x_gus_autocomplete(self, query, timeout=15):
        parsed_nip = self._x_pl_parse_vat(query)
        if parsed_nip:
            return self._x_pl_get_gus_data(nip=parsed_nip, timeout=timeout) or []

        return []

    @api.model
    def enrich_company(self, company_domain, partner_gid, vat, timeout=15):
        account_id = self.env['iap.account'].get('partner_autocomplete')
        if not account_id.account_token:
            return {}
        else:
            return super().enrich_company(company_domain, partner_gid, vat, timeout)

    @staticmethod
    def _x_pl_parse_vat(vat: str) -> Optional[str]:
        if matcher := re.match(r'^((?i:PL)?(?P<nip>\d{10}))$', re.sub(r'[-\s]', '', vat)):
            return matcher.groupdict()['nip']

    @staticmethod
    def x_pl_validate_vat(vat: str, raise_exception=False) -> str:
        if vat:
            try:
                return std_pl_nip.validate(ResPartner._x_pl_parse_vat(vat))
            except std_pl_nip.ValidationError as error:
                if raise_exception:
                    raise ValidationError(str(error)) from error

        elif raise_exception:
            raise ValidationError(_('Please provide VAT'))

    # noinspection PyMethodMayBeStatic
    def _x_pl_check_action(self, record_id, title):
        return {
            'name': title,
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'trilab.check.partner',
            'res_id': record_id,
            'target': 'new',
        }

    def x_pl_update_gus_action(self):
        poland_id = self.env.ref('base.pl')
        partner_ids = self.filtered(lambda partner_id: partner_id.country_id == poland_id and partner_id.vat)

        errors = partner_ids.x_pl_update_gus_data()

        if self.env.context.get('no_confirm', False) and not errors:
            return {}

        if not partner_ids:
            raise UserError(_('Please select partner'))

        record_id = self.env['trilab.check.partner'].create(
            {
                'check_ids': [
                    fields.Command.create(
                        {
                            'partner_id': partner_id.id,
                            'gus_selection_ids': [
                                fields.Command.create({'partner_id': partner_id.id, **err})
                                for err in errors.get(partner_id.id, {}).get('records', {})
                            ],
                            'error_type': errors.get(partner_id.id, {}).get('error_type'),
                            'error_message': errors.get(partner_id.id, {}).get('error_message'),
                        }
                    )
                    for partner_id in partner_ids
                ],
                'mode': 'gus',
            }
        )

        for check_id in record_id.check_ids.filtered(lambda rec_id: len(rec_id.gus_selection_ids) == 1):
            check_id.gus_selected_id = fields.first(check_id.gus_selection_ids)

        if len(partner_ids) > 1:
            return partner_ids._x_pl_check_action(record_id=record_id.id, title=_('Updated data from GUS'))

        else:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'trilab.check.partner.details',
                'views': [[False, 'form']],
                'view_mode': 'form',
                'res_id': record_id.check_ids.id,
                'target': 'new',
            }

    # noinspection DuplicatedCode
    def x_pl_check_nip_action(self):
        poland_id = self.env.ref('base.pl')
        partner_ids = self.filtered(lambda partner_id: partner_id.country_id == poland_id and partner_id.vat)

        errors = partner_ids.x_pl_check_mf_nip(raise_exception=False, post_change=True)

        if self.env.context.get('no_confirm', False) and not errors:
            return {}

        rec = [
            fields.Command.create(
                {
                    'partner_id': partner_id.id,
                    'error_type': errors.get(partner_id.id, {}).get('error_type'),
                    'error_message': errors.get(partner_id.id, {}).get('error_message'),
                }
            )
            for partner_id in partner_ids
        ]

        new_record_id = self.env['trilab.check.partner'].create({'check_ids': rec, 'mode': 'nip'})

        # noinspection PyProtectedMember
        return partner_ids._x_pl_check_action(record_id=new_record_id.id, title=_('MF VAT Validation Results'))

    # noinspection DuplicatedCode
    def x_pl_check_vies_action(self):
        partner_ids = self.filtered('vat')
        errors = partner_ids.x_pl_check_vies(raise_exception=False)

        if self.env.context.get('no_confirm', False) and not errors:
            return {}

        check_rec_id = self.env['trilab.check.partner'].create(
            {
                'check_ids': [
                    fields.Command.create(
                        {
                            'partner_id': partner_id.id,
                            'error_type': errors.get(partner_id.id, {}).get('error_type'),
                            'error_message': errors.get(partner_id.id, {}).get('error_message'),
                        }
                    )
                    for partner_id in partner_ids
                ],
                'mode': 'vies',
            }
        )

        # noinspection PyProtectedMember
        return partner_ids._x_pl_check_action(record_id=check_rec_id.id, title=_('VIES Validation Results'))

    def x_pl_get_bank_accounts(self):
        self.ensure_one()

        nip = self.x_pl_validate_vat(self.vat)
        if not nip:
            raise ValidationError(_('Invalid VAT number'))

        # https://wl-api.mf.gov.pl/api/search/nip/{nip}?date={date}
        response = requests.get(
            f'{MF_WL_PROD_URL}api/search/nip/{nip}', params={'date': fields.Date.today().isoformat()}
        )
        response_json = response.json()

        if response.ok:
            bank_accounts = (response_json.get('result', {}).get('subject') or {}).get('accountNumbers', [])
            if bank_accounts:
                bank_accounts = list(
                    filter(lambda x: f'PL{x}' not in self.bank_ids.mapped('sanitized_acc_number'), bank_accounts)
                )
                if len(bank_accounts) == 1:
                    self.bank_ids.create({'acc_number': bank_accounts[0], 'partner_id': self.id})
                    self.message_post(
                        body=_('Bank account added from Whitelist of Ministry of Finance: %s', bank_accounts[0])
                    )

                elif len(bank_accounts) > 1:
                    wizard = self.env['trilab.wl.wizard'].create({'partner_id': self.id})

                    wizard.write(
                        {
                            'banks_ids': [
                                fields.Command.create({'wl_wizard_id': wizard.id, 'acc_number': bank_account})
                                for bank_account in bank_accounts
                            ]
                        }
                    )

                    return {
                        'name': _('Select Whitelist Bank Accounts To Save'),
                        'type': 'ir.actions.act_window',
                        'res_model': 'trilab.wl.wizard',
                        'res_id': wizard.id,
                        'view_mode': 'form',
                        'target': 'new',
                    }

            else:
                raise ValidationError(_('No bank accounts found for VAT id: %s', nip))

        else:
            raise ValidationError(_('Error occurred: %s', response_json))
