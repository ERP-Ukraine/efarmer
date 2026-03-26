import base64
import datetime
import re

from lxml import etree
from odoo import _, fields, models, release
from odoo.exceptions import UserError
from odoo.tools import float_repr, float_round

FLAGS = [
    'GTU_01',
    'GTU_02',
    'GTU_03',
    'GTU_04',
    'GTU_05',
    'GTU_06',
    'GTU_07',
    'GTU_08',
    'GTU_09',
    'GTU_10',
    'GTU_11',
    'GTU_12',
    'GTU_13',
    'TP',
    'TT_WNT',
    'TT_D',
    'MR_T',
    'MR_UZ',
    'I_42',
    'I_63',
    'B_SPV',
    'B_SPV_DOSTAWA',
    'B_MPV_PROWIZJA',
    'KorektaPodstawyOpodt',
    'IMP',
    'WSTO_EE',
    'IED',
]

EMPTY = 'BRAK'

REQUIRED_TOGETHER = {
    'P_11': 'P_12',
    'P_13': 'P_14',
    'P_15': 'P_16',
    'P_17': 'P_18',
    'P_19': 'P_20',
    'P_23': 'P_24',
    'P_25': 'P_26',
    'P_29': 'P_30',
    'P_31': 'P_32',
    'P_37': 'P_38',
    'P_40': 'P_41',
    'P_42': 'P_43',
    'K_15': 'K_16',
    'K_17': 'K_18',
    'K_19': 'K_20',
    'K_23': 'K_24',
    'K_25': 'K_26',
    'K_27': 'K_28',
    'K_29': 'K_30',
    'K_31': 'K_32',
    'K_40': 'K_41',
    'K_42': 'K_43',
}


class JpkReportV3(models.AbstractModel):
    _name = 'account.report.jpk_vat7m_v3'
    _inherit = 'account.report.jpk_vat7m'
    _description = 'JPK VAT 7M (3) 1.0E Report'

    grouping_columns = [
        'nrkontrahenta',
        'nazwakontrahenta',
        'dowodsprzedazyzakupu',
        'datawystawienia',
        'datasprzedazy',
        'datazakupu',
        'datawplywu',
        'terminplatnosci',
        'typdokumentu',
        'flags',
        'ksefdowod',
    ]
    detail_columns = ['nrksef', 'gtu', 'jpkmarkup', 'jpkgroup', 'kwota']
    all_columns = grouping_columns + detail_columns

    _column_class = [
        'text',
        'text',
        'text',
        'date',
        'date',
        'date',
        'date',
        'date',
        'text',
        'text',
        'text',
        'text',
        'text',
        'text',
        'text',
        'text',
    ]

    column_class = dict(zip(all_columns, _column_class))

    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    def _get_columns_name(self, options):
        columns_header = [
            {'name': 'Sekcja JPK'},
            {'name': '#'},
            {'name': 'NrKontrahenta'},
            {'name': 'NazwaKontrahenta'},
            {'name': 'DowodSprzedazyZakupu'},
            {'name': 'DataWystawienia'},
            {'name': 'DataSprzedazy'},
            {'name': 'DataZakupu'},
            {'name': 'DataWplywu'},
            {'name': 'TerminPlatnosci'},
            {'name': 'TypDokumentu'},
            {'name': 'Procedury'},
            {'name': 'DowodKSeF'},
            {'name': 'NrKSeF'},
            {'name': 'GTU'},
            {'name': 'JPKMarkup'},
            {'name': 'JPKGroup'},
            {'name': 'kwota', 'class': 'number'},
        ]
        return columns_header

    @staticmethod
    def _get_query():
        return """SELECT am.id                                    AS gid,
                         jat.jpk_section                          AS JPKSection,
                         p.vat                                    AS NrKontrahenta,
                         p.name                                   AS NazwaKontrahenta,
                         p.id                                     AS PartnerId,
                         (CASE
                              WHEN am.x_pl_change_jpk_proof IS NOT NULL
                                  THEN am.x_pl_change_jpk_proof
                              WHEN aj.type = 'sale'
                                  THEN am.name
                              ELSE aml.ref
                             END)                                 AS DowodSprzedazyZakupu,
                         am.x_pl_ksef_invoice_number              AS NrKSeF,
                         am.x_pl_ksef_invoice_proof               AS KSeFDowod,
                         coalesce(am.invoice_date, am.date)       AS DataWystawienia,
                         am.x_invoice_sale_date                   AS DataSprzedazy,
                         am.invoice_date                          AS DataZakupu,
                         am.pl_vat_date                           AS DataWplywu,
                         (CASE
                              WHEN aml.tax_line_id IS NOT NULL
                                  then TRUE
                              ELSE FALSE
                             END)                                 AS isTax,
                         jat.jpk_markup                           AS JPKMarkup,
                         jat.jpk_v7_group                         AS JPKGroup,
                         (CASE
                              WHEN jat.jpk_section = 'SprzedazWiersz'
                                  THEN am.x_pl_vat_typ_dokumentu
                              ELSE am.x_pl_vat_dokument_zakupu
                             END)                                 AS TypDokumentu,
                         STRING_AGG(distinct (jpk_gtu.name), ',') AS GTU,
                         CONCAT_WS(',', CASE WHEN am.x_pl_vat_tp AND jat.jpk_section = 'SprzedazWiersz' THEN 'TP' END,
                                   CASE \
                                       WHEN am.x_pl_vat_tt_wnt AND jat.jpk_section = 'SprzedazWiersz' THEN 'TT_WNT' END,
                                   CASE WHEN am.x_pl_vat_tt_d THEN 'TT_D' END,
                                   CASE WHEN am.x_pl_vat_mr_t THEN 'MR_T' END,
                                   CASE WHEN am.x_pl_vat_mr_uz THEN 'MR_UZ' END,
                                   CASE WHEN am.x_pl_vat_i42 THEN 'I_42' END,
                                   CASE WHEN am.x_pl_vat_i63 THEN 'I_63' END,
                                   CASE WHEN am.x_pl_vat_b_spv THEN 'B_SPV' END,
                                   CASE WHEN am.x_pl_vat_b_spv_dostawa THEN 'B_SPV_DOSTAWA' END,
                                   CASE WHEN am.x_pl_vat_b_mpv_prowizja THEN 'B_MPV_PROWIZJA' END,
                                   CASE \
                                       WHEN am.x_pl_vat_korekta_podstawy_opodt AND jat.jpk_section = 'SprzedazWiersz' \
                                           THEN 'KorektaPodstawyOpodt' END,
                                   CASE WHEN am.x_pl_vat_imp AND jat.jpk_section = 'ZakupWiersz' THEN 'IMP' END,
                                   CASE WHEN am.x_pl_vat_wsto_ee THEN 'WSTO_EE' END,
                                   CASE WHEN am.x_pl_vat_ied THEN 'IED' END
                         )                                        AS Flags,
                         SUM(CASE
                                 WHEN aml.tax_line_id IS NOT NULL AND jat.jpk_section = 'ZakupWiersz'
                                     then aml.balance
                                 WHEN aml.tax_line_id IS NOT NULL AND jat.jpk_section = 'SprzedazWiersz'
                                     then - aml.balance
                                 WHEN jat.jpk_section = 'SprzedazWiersz' AND \
                                      am.move_type IN ('out_invoice', 'out_refund', 'entry')
                                     THEN - aml.balance
                                 ELSE (aml.balance)
                             END)                                 AS kwota,
                         am.invoice_date_due                      AS TerminPlatnosci
                  FROM account_move AS am
                           LEFT JOIN res_partner p ON am.partner_id = p.id
                           LEFT JOIN account_journal aj ON am.journal_id = aj.id
                           LEFT JOIN account_move_line aml ON aml.move_id = am.id
                           LEFT OUTER JOIN jpk_gtu ON jpk_gtu.id = aml.x_pl_vat_gtu
                           LEFT JOIN account_account_tag_account_move_line_rel aatmr \
                                     ON aatmr.account_move_line_id = aml.id
                           LEFT JOIN account_account_tag aat ON aat.id = aatmr.account_account_tag_id
                           LEFT OUTER JOIN jpk_account_tag jat ON jat.account_tag_id = aat.id
                           LEFT JOIN account_tax tax ON tax.id = aml.tax_line_id
                  WHERE am.state IN %(allowed_states)s
                    AND jat.jpk_document_type = %(jpk_doc_id)s
                    AND aj.type IN %(journal_types)s
                    AND am.pl_vat_date >= %(date_from)s
                    AND am.pl_vat_date <= %(date_to)s
                    AND am.company_id = %(company)s
                    AND coalesce(aml.display_type, '') != ANY ('{"line_section", "line_note"}') -- such as aml.display_type can be NULL or string we must use coalesce for correct ANY comparing
                  GROUP BY am.id, JPKSection, NrKontrahenta, NazwaKontrahenta, PartnerId, DowodSprzedazyZakupu, NrKSeF, \
                           KSeFDowod,
                           DataWystawienia, DataSprzedazy, DataZakupu, DataWplywu, isTax, TypDokumentu, Flags, \
                           JPKMarkup, JPKGroup,
                           TerminPlatnosci
                  ORDER BY JPKsection, DataWystawienia, am.id, DowodSprzedazyZakupu, JPKMarkup, JPKGroup"""

    # noinspection HttpUrlsUsage
    def get_xml_extended(self, options):
        tns = 'http://crd.gov.pl/wzor/2025/12/19/14090/'
        xsi = 'http://www.w3.org/2001/XMLSchema-instance'
        etd = 'http://crd.gov.pl/xml/schematy/dziedzinowe/mf/2022/09/13/eD/DefinicjeTypy/'
        kus = 'http://crd.gov.pl/xml/schematy/dziedzinowe/mf/2022/01/05/eD/KodyUrzedowSkarbowych/'
        kk = 'http://crd.gov.pl/xml/schematy/dziedzinowe/mf/2023/09/06/eD/KodyKrajow/'
        schema_location = 'http://crd.gov.pl/wzor/2025/12/19/14090/schemat.xsd'

        company = self.env.company
        jpk = etree.Element(
            etree.QName(tns, 'JPK'),
            attrib={etree.QName(xsi, 'schemaLocation'): schema_location},
            nsmap={'tns': tns, 'xsi': xsi, 'etd': etd, 'kus': kus, 'kk': kk},
        )

        header = etree.SubElement(jpk, etree.QName(tns, 'Naglowek'))

        etree.SubElement(
            header, etree.QName(tns, 'KodFormularza'), attrib={'kodSystemowy': 'JPK_V7M (3)', 'wersjaSchemy': '1-0E'}
        ).text = 'JPK_VAT'
        etree.SubElement(header, etree.QName(tns, 'WariantFormularza')).text = '3'
        etree.SubElement(header, etree.QName(tns, 'DataWytworzeniaJPK')).text = datetime.datetime.now().isoformat()
        etree.SubElement(header, etree.QName(tns, 'NazwaSystemu')).text = f'{release.description} {release.version}'
        etree.SubElement(
            header, etree.QName(tns, 'CelZlozenia'), attrib={'poz': 'P_7'}
        ).text = f'{options.get("submit_purpose", 1)}'

        if not company.pl_tax_office_id.code:
            raise UserError(_('PL Tax Office is not set for company %s', company.name))

        etree.SubElement(header, etree.QName(tns, 'KodUrzedu')).text = company.pl_tax_office_id.code

        report_date = fields.Date.to_date(options['date']['date_from'])
        etree.SubElement(header, etree.QName(tns, 'Rok')).text = str(report_date.year)
        etree.SubElement(header, etree.QName(tns, 'Miesiac')).text = str(report_date.month)

        podmiot = etree.SubElement(jpk, etree.QName(tns, 'Podmiot1'), attrib={'rola': 'Podatnik'})
        podmiot_sub = etree.SubElement(podmiot, etree.QName(tns, 'OsobaNiefizyczna'))

        try:
            etree.SubElement(podmiot_sub, etree.QName(tns, 'NIP')).text = re.sub(r'\D', '', company.vat)
        except TypeError as error:
            raise UserError(_("Make sure that Company's VAT number is correct")) from error

        etree.SubElement(podmiot_sub, etree.QName(tns, 'PelnaNazwa')).text = company.name

        # common
        etree.SubElement(podmiot_sub, etree.QName(tns, 'Email')).text = company.x_get_jpk_email()

        if company.phone:
            etree.SubElement(podmiot_sub, etree.QName(tns, 'Telefon')).text = company.phone

        deklaracja = etree.SubElement(jpk, etree.QName(tns, 'Deklaracja'))
        deklaracja_naglowek = etree.SubElement(deklaracja, etree.QName(tns, 'Naglowek'))

        etree.SubElement(
            deklaracja_naglowek,
            etree.QName(tns, 'KodFormularzaDekl'),
            attrib={
                'kodSystemowy': 'VAT-7 (23)',
                'kodPodatku': 'VAT',
                'rodzajZobowiazania': 'Z',
                'wersjaSchemy': '1-0E',
            },
        ).text = 'VAT-7'

        etree.SubElement(deklaracja_naglowek, etree.QName(tns, 'WariantFormularzaDekl')).text = '23'
        pozycje_szczegolowe = etree.SubElement(deklaracja, etree.QName(tns, 'PozycjeSzczegolowe'))
        etree.SubElement(deklaracja, etree.QName(tns, 'Pouczenia')).text = '1'

        ewidencja = etree.SubElement(jpk, etree.QName(tns, 'Ewidencja'))

        ctx = self._set_context(options)

        # deactivating the prefetching saves ~35% on get_lines running time
        ctx.update({'no_format': True, 'print_mode': False, 'prefetch_fields': False, 'dict_output': True})
        # noinspection PyProtectedMember
        sections = self.with_context(ctx)._get_lines(options)

        declaration_groups = {}

        # SprzedazWiersz
        section_count = 0
        section_sum = 0.0

        for line in sections.get('SprzedazWiersz', []):
            section_count += 1
            sale_row = etree.SubElement(ewidencja, etree.QName(tns, 'SprzedazWiersz'))
            etree.SubElement(sale_row, etree.QName(tns, 'LpSprzedazy')).text = str(line['counter'])

            _partner = line['data']['partnerid'] and self.env['res.partner'].browse(line['data']['partnerid'])

            if eu_vat := _partner and _partner.x_get_eu_vat():
                _country_code, _vat = eu_vat[:2], eu_vat[2:]
            elif not eu_vat and _partner:
                # _vat = _partner.vat and self._sanitize_vat(_partner.vat) or None
                _vat = _partner.vat and self.env['res.partner']._fix_vat_number(_partner.vat, _partner.country_id.id) or None
                _country_code = _partner.country_id.code
            else:
                _vat = _country_code = None

            _taxes = set()
            _flags = set()

            if _country_code:
                etree.SubElement(sale_row, etree.QName(tns, 'KodKrajuNadaniaTIN')).text = _country_code

            etree.SubElement(sale_row, etree.QName(tns, 'NrKontrahenta')).text = _vat or EMPTY

            etree.SubElement(sale_row, etree.QName(tns, 'NazwaKontrahenta')).text = (
                    line['data']['nazwakontrahenta'] or EMPTY
            )

            etree.SubElement(sale_row, etree.QName(tns, 'DowodSprzedazy')).text = (
                    line['data']['dowodsprzedazyzakupu'] or EMPTY
            )

            etree.SubElement(sale_row, etree.QName(tns, 'DataWystawienia')).text = line['data'][
                'datawystawienia'
            ].isoformat()

            if (
                    line['data']['datasprzedazy']
                    and line['data']['datawystawienia']
                    and line['data']['datasprzedazy'] != line['data']['datawystawienia']
            ):
                etree.SubElement(sale_row, etree.QName(tns, 'DataSprzedazy')).text = line['data'][
                    'datasprzedazy'
                ].isoformat()

            if line['data']['nrksef']:
                etree.SubElement(sale_row, etree.QName(tns, 'NrKSeF')).text = line['data']['nrksef']
            elif not (line['data']['ksefdowod'] or line['data']['ksefdowod']):
                etree.SubElement(sale_row, etree.QName(tns, 'OFF')).text = '1'
            else:
                etree.SubElement(sale_row, etree.QName(tns, line['data']['ksefdowod'])).text = '1'

            if line['data']['typdokumentu']:
                etree.SubElement(sale_row, etree.QName(tns, 'TypDokumentu')).text = line['data']['typdokumentu']

            for child in line['children']:
                if child['flags']:
                    _flags.update(child['flags'].split(','))

                if child['gtu']:
                    _flags.update(child['gtu'].split(','))

                if child['jpkgroup']:
                    if child['istax']:
                        section_sum += child['kwota']

                    declaration_groups.setdefault(child['jpkgroup'], 0.0)
                    declaration_groups[child['jpkgroup']] += child['kwota']

                if child['jpkmarkup']:
                    _taxes.add((child['jpkmarkup'], child['kwota']))

            for flag in filter(lambda f: f in _flags, FLAGS):
                etree.SubElement(sale_row, etree.QName(tns, flag)).text = '1'
                if flag == 'KorektaPodstawyOpodt' and line['data']['terminplatnosci']:
                    etree.SubElement(sale_row, etree.QName(tns, 'TerminPlatnosci')).text = line['data'][
                        'terminplatnosci'
                    ].isoformat()

            for tag, value in sorted(self.fix_required_tags(_taxes), key=lambda x: x[0]):
                etree.SubElement(sale_row, etree.QName(tns, tag)).text = float_repr(value, 2)

        section = etree.SubElement(ewidencja, etree.QName(tns, 'SprzedazCtrl'))
        etree.SubElement(section, etree.QName(tns, 'LiczbaWierszySprzedazy')).text = f'{section_count:d}'
        etree.SubElement(section, etree.QName(tns, 'PodatekNalezny')).text = f'{section_sum:.2f}'

        # ZakupWiersz
        section_count = 0
        section_sum = 0.0

        for line in sections.get('ZakupWiersz', []):
            section_count += 1
            purchase_row = etree.SubElement(ewidencja, etree.QName(tns, 'ZakupWiersz'))
            etree.SubElement(purchase_row, etree.QName(tns, 'LpZakupu')).text = str(line['counter'])

            _partner = line['data']['partnerid'] and self.env['res.partner'].browse(line['data']['partnerid'])

            if eu_vat := _partner and _partner.x_get_eu_vat():
                _country_code, _vat = eu_vat[:2], eu_vat[2:]
            elif not eu_vat and _partner:
                # _vat = _partner.vat and self._sanitize_vat(_partner.vat) or None
                _vat = _partner.vat and self.env['res.partner']._fix_vat_number(_partner.vat, _partner.country_id.id) or None
                _country_code = _partner.country_id.code
            else:
                _vat = _country_code = None

            _taxes = set()
            _flags = set()

            if _country_code:
                etree.SubElement(purchase_row, etree.QName(tns, 'KodKrajuNadaniaTIN')).text = _country_code

            etree.SubElement(purchase_row, etree.QName(tns, 'NrDostawcy')).text = _vat or EMPTY

            etree.SubElement(purchase_row, etree.QName(tns, 'NazwaDostawcy')).text = (
                    line['data']['nazwakontrahenta'] or EMPTY
            )

            etree.SubElement(purchase_row, etree.QName(tns, 'DowodZakupu')).text = line['data']['dowodsprzedazyzakupu']

            etree.SubElement(purchase_row, etree.QName(tns, 'DataZakupu')).text = line['data']['datazakupu'].isoformat()

            if (
                    line['data']['datawplywu']
                    and line['data']['datazakupu']
                    and line['data']['datawplywu'] != line['data']['datazakupu']
            ):
                etree.SubElement(purchase_row, etree.QName(tns, 'DataWplywu')).text = line['data'][
                    'datawplywu'
                ].isoformat()

            if line['data']['nrksef']:
                etree.SubElement(purchase_row, etree.QName(tns, 'NrKSeF')).text = line['data']['nrksef']
            elif not (line['data']['ksefdowod'] or line['data']['ksefdowod']):
                etree.SubElement(purchase_row, etree.QName(tns, 'OFF')).text = '1'
            else:
                etree.SubElement(purchase_row, etree.QName(tns, line['data']['ksefdowod'])).text = '1'

            if line['data']['typdokumentu']:
                etree.SubElement(purchase_row, etree.QName(tns, 'DokumentZakupu')).text = line['data']['typdokumentu']

            for child in line['children']:
                if child['flags']:
                    _flags.update(child['flags'].split(','))

                if child['gtu']:
                    _flags.update(child['gtu'].split(','))

                if child['jpkgroup']:
                    if child['istax']:
                        section_sum += child['kwota']

                    declaration_groups.setdefault(child['jpkgroup'], 0.0)
                    declaration_groups[child['jpkgroup']] += child['kwota']

                if child['jpkmarkup']:
                    _taxes.add((child['jpkmarkup'], child['kwota']))

            for flag in filter(lambda f: f in _flags, FLAGS):
                etree.SubElement(purchase_row, etree.QName(tns, flag)).text = '1'

            for tag, value in sorted(self.fix_required_tags(_taxes), key=lambda x: x[0]):
                etree.SubElement(purchase_row, etree.QName(tns, tag)).text = float_repr(value, 2)

        section = etree.SubElement(ewidencja, etree.QName(tns, 'ZakupCtrl'))
        etree.SubElement(section, etree.QName(tns, 'LiczbaWierszyZakupow')).text = f'{section_count:d}'
        etree.SubElement(section, etree.QName(tns, 'PodatekNaliczony')).text = f'{section_sum:.2f}'

        for tag, amount in declaration_groups.items():
            int_amount = declaration_groups[tag] = int(float_round(amount, 0))
            etree.SubElement(pozycje_szczegolowe, etree.QName(tns, tag.upper())).text = str(int_amount)

        return etree.tostring(jpk, encoding='UTF-8', xml_declaration=True, pretty_print=True), declaration_groups

    def export_xml(self, options):
        report_date = fields.Date.to_date(options['date']['date_from'])

        xml, sums = self.get_xml_extended(options)
        sums = {k.lower(): v for k, v in sums.items()}

        v7m_report = self.env['jpk.vat.7m'].create(
            {
                'version': '1-0E',
                'technical_version': 'v3',
                'year': report_date.year,
                'month': report_date.month,
                'cel_zlozenia': options.get('cel_zlozenia', 1),
                'document_type_id': self.env.ref('trilab_jpk_base.jpk_v7m_3_1_0e_doc_type').id,
                'source_xml': base64.b64encode(xml),
                **sums,
            }
        )

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'jpk.vat.7m',
            'views': [[False, 'form']],
            'name': 'JPK VAT 7M',
            'res_id': v7m_report.id,
            'target': 'new',
        }

    @staticmethod
    def fix_required_tags(tags):
        result = []
        existing_tags = [t[0] for t in tags]

        for tag in tags:
            result.append(tag)
            required = REQUIRED_TOGETHER.get(tag[0])
            if required and required not in existing_tags:
                result.append((required, 0.0))

        return result
