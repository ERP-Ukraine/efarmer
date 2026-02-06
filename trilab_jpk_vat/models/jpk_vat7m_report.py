import base64
import datetime
import io
import json
import re

import xlsxwriter
from lxml import etree

from odoo import _, api, fields, models, release
from odoo.addons.web.controllers.main import clean_action
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
    'SW',
    'EE',
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
    'MPP',
    'KorektaPodstawyOpodt',
    'IMP',
]


# noinspection DuplicatedCode
class JpkReport(models.AbstractModel):
    _inherit = 'account.report'
    _name = 'account.report.jpk_vat7m'
    _description = 'JPK VAT 7M Report'

    filter_multi_company = True
    filter_date = {'date_from': '', 'date_to': '', 'filter': 'last_month', 'mode': 'range'}
    filter_cel_zlozenia = '1'
    filter_all_entries = False
    filter_unfold_all = False

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
    ]
    detail_columns = ['gtu', 'jpkmarkup', 'jpkgroup', 'kwota']
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
            {'name': 'GTU'},
            {'name': 'JPKMarkup'},
            {'name': 'JPKGroup'},
            {'name': 'kwota', 'class': 'number'},
        ]
        return columns_header

    @staticmethod
    def _get_query():
        # noinspection SqlResolve
        return """SELECT am.id                  AS gid,
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
       am.invoice_date                          AS DataWystawienia,
       am.pl_vat_date                           AS DataSprzedazy,
       am.invoice_date                          AS DataZakupu,
       am.pl_vat_date                           AS DataWplywu,
       (CASE
            WHEN aml.tax_line_id IS NOT NULL
                THEN TRUE
            ELSE FALSE
           END)                                 AS isTax,
       jat.jpk_markup                           AS JPKMarkup,
       jat.jpk_v7_group                         AS JPKGroup,
       (CASE
            WHEN jat.jpk_section = 'SprzedazWiersz'
                THEN am.x_pl_vat_typ_dokumentu
            ELSE am.x_pl_vat_dokument_zakupu
           END)                                 AS TypDokumentu,
       STRING_AGG(DISTINCT (jpk_gtu.name), ',') AS GTU,
       CONCAT_WS(',', CASE WHEN am.x_pl_vat_sw THEN 'SW' END,
                 CASE WHEN am.x_pl_vat_ee THEN 'EE' END,
                 CASE WHEN am.x_pl_vat_tp AND jat.jpk_section = 'SprzedazWiersz' THEN 'TP' END,
                 CASE WHEN am.x_pl_vat_tt_wnt AND jat.jpk_section = 'SprzedazWiersz' THEN 'TT_WNT' END,
                 CASE WHEN am.x_pl_vat_tt_d THEN 'TT_D' END,
                 CASE WHEN am.x_pl_vat_mr_t THEN 'MR_T' END,
                 CASE WHEN am.x_pl_vat_mr_uz THEN 'MR_UZ' END,
                 CASE WHEN am.x_pl_vat_i42 THEN 'I_42' END,
                 CASE WHEN am.x_pl_vat_i63 THEN 'I_63' END,
                 CASE WHEN am.x_pl_vat_b_spv THEN 'B_SPV' END,
                 CASE WHEN am.x_pl_vat_b_spv_dostawa THEN 'B_SPV_DOSTAWA' END,
                 CASE WHEN am.x_pl_vat_b_mpv_prowizja THEN 'B_MPV_PROWIZJA' END,
                 CASE
                     WHEN am.x_pl_vat_korekta_podstawy_opodt AND jat.jpk_section = 'ZakupWiersz'
                         THEN 'KorektaPodstawyOpodt' END,
                 CASE WHEN am.x_pl_vat_mpp THEN 'MPP' END,
                 CASE WHEN am.x_pl_vat_imp AND jat.jpk_section = 'ZakupWiersz' THEN 'IMP' END
           )                                    AS Flags,
       SUM(CASE
               WHEN aml.tax_line_id IS NOT NULL AND jat.jpk_section = 'ZakupWiersz'
                   THEN aml.balance
               WHEN aml.tax_line_id IS NOT NULL AND jat.jpk_section = 'SprzedazWiersz'
                   THEN - aml.balance
               WHEN jat.jpk_section = 'SprzedazWiersz' AND am.move_type IN ('out_invoice', 'out_refund', 'entry')
                   THEN - aml.balance
               ELSE (aml.balance)
           END)                                 AS kwota,
           am.invoice_date_due                  AS TerminPlatnosci
FROM account_move AS am
         LEFT JOIN res_partner p ON am.partner_id = p.id
         LEFT JOIN account_journal aj ON am.journal_id = aj.id
         LEFT JOIN account_move_line aml ON aml.move_id = am.id
         LEFT OUTER JOIN jpk_gtu ON jpk_gtu.id = aml.x_pl_vat_gtu
         LEFT JOIN account_account_tag_account_move_line_rel aatmr ON aatmr.account_move_line_id = aml.id
         LEFT JOIN account_account_tag aat ON aat.id = aatmr.account_account_tag_id
         LEFT OUTER JOIN jpk_account_tag jat ON jat.account_tag_id = aat.id
         LEFT JOIN account_tax tax ON tax.id = aml.tax_line_id
WHERE am.state IN %(allowed_states)s
         AND jat.jpk_document_type = %(jpk_doc_id)s
         AND aj.type IN %(journal_types)s
         AND am.pl_vat_date >= %(date_from)s
         AND am.pl_vat_date <= %(date_to)s
         AND am.company_id = %(company)s
         AND aml.display_type IS NULL
GROUP BY am.id, JPKSection, NrKontrahenta, NazwaKontrahenta, PartnerId, DowodSprzedazyZakupu, DataWystawienia,
         DataSprzedazy, DataZakupu, DataWplywu, isTax, TypDokumentu, Flags, JPKMarkup, JPKGroup, TerminPlatnosci
ORDER BY JPKsection, DataWystawienia, am.id, DowodSprzedazyZakupu, JPKMarkup, JPKGroup"""

    # noinspection PyUnusedLocal
    @api.model
    def _get_lines(self, options, line_id=None):
        context = self.env.context
        query = self._get_query()
        params = {
            'jpk_doc_id': self.env.ref('trilab_jpk_base.jpk_v7m_1_2_doc_type').id,
            'journal_types': ('sale', 'purchase'),
            'date_from': context.get('date_from'),
            'date_to': context.get('date_to'),
            'company': self.env.company.id,
            'allowed_states': ('posted', 'draft') if options.get('all_entries') else ('posted',),
        }

        lines_offset = options.get('lines_offset', 0)
        lines_limit = context.get('lines_limit')

        if lines_offset:
            query += ' OFFSET %(lines_offset)s'
            params['lines_offset'] = lines_offset

        if lines_limit:
            query += ' LIMIT %(lines_limit)s'
            params['lines_limit'] = lines_limit

        self.env.cr.execute(query, params)

        dict_output = context.get('dict_output', False)
        master_subsection_empty = [{}] * len(self.detail_columns)
        children_subsection_empty = [{}] * (len(self.grouping_columns) + 1)

        lines = {}
        section_counter = options.get('lines_remaining', {})
        master_line = False
        jpk_section = 'BRAK'
        gid = None

        if not options.get('x_no_groupby'):
            for row in self.env.cr.dictfetchall():
                lines_offset += 1
                if gid != row['gid'] or jpk_section != row['jpksection']:
                    master_line = False

                    gid = row['gid']
                    jpk_section = row['jpksection']
                    lines.setdefault(jpk_section, [])
                    section_counter.setdefault(jpk_section, 0)
                    section_counter[jpk_section] += 1

                if not dict_output:
                    if jpk_section == 'SprzedazWiersz':
                        row['datawplywu'] = row['datazakupu'] = None
                    elif jpk_section == 'ZakupWiersz':
                        row['datasprzedazy'] = row['datawystawienia'] = None

                if not master_line:
                    if dict_output:
                        lines[jpk_section].append(
                            {'data': row, 'counter': section_counter[jpk_section], 'children': []}
                        )
                    else:
                        # noinspection PyTypeChecker
                        lines[jpk_section].append(
                            {
                                'id': 'hierarchy',
                                # 'parent_id': f'{jpk_section}:{counter}'),
                                # 'caret_options': 'account.move.line',
                                'model': 'account.move.line',
                                'name': jpk_section,
                                'level': 1,
                                'columns': [{'name': section_counter[jpk_section]}]
                                + [{'name': row[k], 'class': self.column_class[k]} for k in self.grouping_columns]
                                + master_subsection_empty,
                                'unfoldable': False,
                                'unfolded': True,
                                'children': [],
                            }
                        )

                    master_line = True

                if dict_output:
                    lines[jpk_section][-1]['children'].append(row)

                else:
                    # noinspection PyTypeChecker
                    lines[jpk_section][-1]['children'].append(
                        {
                            'id': f"{jpk_section}:{section_counter[jpk_section]}:{row['jpkmarkup']}",
                            # 'caret_options': 'account.move.line',
                            # 'model': 'account.move.line',
                            'depth': 1,
                            # 'name': row['jpkmarkup'],
                            'parent_id': lines[jpk_section][-1]['id'],
                            'columns': children_subsection_empty
                            + [{'name': row[_n], 'class': self.column_class[_n]} for _n in self.detail_columns],
                            'unfoldable': False,
                            'unfolded': False,
                            'isTax': row['istax'],
                        }
                    )

        else:
            for row in self.env.cr.dictfetchall():
                lines_offset += 1
                if gid != row['gid'] or jpk_section != row['jpksection']:
                    master_line = False

                    gid = row['gid']
                    jpk_section = row['jpksection']
                    lines.setdefault(jpk_section, [])
                    section_counter.setdefault(jpk_section, 0)
                    section_counter[jpk_section] += 1

                if jpk_section == 'SprzedazWiersz':
                    row['datawplywu'] = row['datazakupu'] = None
                elif jpk_section == 'ZakupWiersz':
                    row['datasprzedazy'] = row['datawystawienia'] = None

                # noinspection PyTypeChecker
                lines[jpk_section].append(
                    {
                        'id': f"{jpk_section}:{section_counter[jpk_section]}:{row['jpkmarkup']}",
                        'model': 'account.move.line',
                        'name': jpk_section,
                        'level': 1,
                        'columns': [{'name': section_counter[jpk_section]}]
                        + [
                            {'name': row[k], 'class': self.column_class[k]}
                            for k in self.grouping_columns + self.detail_columns
                        ],
                        'unfoldable': False,
                        'unfolded': False,
                        'children': [],
                        'isTax': row['istax'],
                    }
                )

        if not dict_output:
            out_lines = []
            for line in [item for sublist in lines.values() for item in sublist]:
                children = line.pop('children')
                out_lines.append(line)
                out_lines.extend(children)
            if lines_limit:
                out_lines.append(self._get_load_more_line(options, lines_offset, json.dumps(section_counter), 0))
            lines = out_lines
        return lines

    # noinspection PyUnusedLocal
    @api.model
    def _get_super_columns(self, options):
        return {}

    @api.model
    def _create_hierarchy(self, lines):
        return lines

    @api.model
    def _get_report_name(self):
        return _('Jednolity Plik Kontrolny - VAT')

    # noinspection PyMethodMayBeStatic
    def _get_reports_buttons(self, options):
        buttons = [
            {'name': _('Export XLSX - Report'), 'sequence': 1, 'action': 'print_xlsx'},
            {'name': _('Export XLSX - Extract'), 'sequence': 2, 'action': 'print_xlsx_flat'},
            {'name': _('Export XML'), 'sequence': 3, 'action': 'export_xml'},
            {'name': _('Export VAT UE'), 'sequence': 4, 'action': 'export_xml_vat_ue'},
        ]

        if (
            self.env['ir.module.module']
            .sudo()
            .search_count([('name', '=', 'trilab_pl_partners_sync'), ('state', '=', 'installed')])
        ):
            buttons.append({'name': _('Check Partners\' VAT'), 'sequence': 5, 'action': 'check_partners_vat'})

        return buttons

    def get_html(self, options, line_id=None, additional_context=None):
        self = self.with_context(lines_limit=100)
        return super(JpkReport, self).get_html(options, line_id, additional_context)

    # noinspection PyTypeChecker
    def get_xml_extended(self, options):
        # noinspection HttpUrlsUsage
        tns = 'http://crd.gov.pl/wzor/2020/05/08/9393/'
        # noinspection HttpUrlsUsage
        tns_etd = 'http://crd.gov.pl/xml/schematy/dziedzinowe/mf/2016/01/25/eD/DefinicjeTypy/'

        company = self.env.company

        jpk = etree.Element(etree.QName(tns, 'JPK'), nsmap={'tns': tns, 'etd': tns_etd})
        header = etree.SubElement(jpk, etree.QName(tns, 'Naglowek'))

        etree.SubElement(
            header, etree.QName(tns, 'KodFormularza'), attrib={'kodSystemowy': 'JPK_V7M (1)', 'wersjaSchemy': '1-2E'}
        ).text = 'JPK_VAT'
        etree.SubElement(header, etree.QName(tns, 'WariantFormularza')).text = '1'
        etree.SubElement(header, etree.QName(tns, 'DataWytworzeniaJPK')).text = datetime.datetime.now().isoformat()
        etree.SubElement(header, etree.QName(tns, 'NazwaSystemu')).text = f'{release.description} {release.version}'

        etree.SubElement(header, etree.QName(tns, 'CelZlozenia'), attrib={'poz': 'P_7'}).text = (
            f"{options.get('cel_zlozenia', 1)}"
        )

        if not company.pl_tax_office_id.code:
            raise UserError(_('PL Tax Office is not set for company %s', company.name))

        etree.SubElement(header, etree.QName(tns, 'KodUrzedu')).text = company.pl_tax_office_id.code

        report_date = fields.Date.to_date(options['date']['date_from'])
        etree.SubElement(header, etree.QName(tns, 'Rok')).text = str(report_date.year)
        etree.SubElement(header, etree.QName(tns, 'Miesiac')).text = str(report_date.month)

        podmiot = etree.SubElement(jpk, etree.QName(tns, 'Podmiot1'), attrib={'rola': 'Podatnik'})

        # UWAGA tylko dla osób niefizycznych!
        # podmiot_sub = etree.SubElement(jpk, etree.QName(tns, 'OsobaFizyczna'))
        podmiot_sub = etree.SubElement(podmiot, etree.QName(tns, 'OsobaNiefizyczna'))

        try:
            etree.SubElement(podmiot_sub, etree.QName(tns, 'NIP')).text = re.sub(r'\D', '', company.vat)
        except TypeError:
            raise UserError(_("Make sure that Company's VAT number is correct"))

        # noinspection PyUnreachableCode
        if False:  # osoba fizyczna todo dodać warunek
            _parts = company.name.split()
            etree.SubElement(podmiot_sub, etree.QName(tns, 'ImiePierwsze')).text = _parts[0]
            etree.SubElement(podmiot_sub, etree.QName(tns, 'Nazwisko')).text = ' '.join(_parts[1:]) if _parts else ''
            etree.SubElement(podmiot_sub, etree.QName(tns, 'DataUrodzenia')).text = None  # todo skąd wziąć?
        else:  # osoba niefizyczna
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
                'kodSystemowy': 'VAT-7 (21)',
                'kodPodatku': 'VAT',
                'rodzajZobowiazania': 'Z',
                'wersjaSchemy': '1-2E',
            },
        ).text = 'VAT-7'

        etree.SubElement(deklaracja_naglowek, etree.QName(tns, 'WariantFormularzaDekl')).text = '21'
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

            _vat = line['data']['nrkontrahenta']
            _country = None
            _flags = set(line['data']['flags'].split(',')) if line['data']['flags'] else set()
            _taxes = set()

            if line['data']['partnerid']:
                _country = self.env['res.partner'].browse(line['data']['partnerid']).x_get_eu_vat_country()

            if _country:
                etree.SubElement(sale_row, etree.QName(tns, 'KodKrajuNadaniaTIN')).text = _country

            etree.SubElement(sale_row, etree.QName(tns, 'NrKontrahenta')).text = _vat or 'BRAK'
            etree.SubElement(sale_row, etree.QName(tns, 'NazwaKontrahenta')).text = (
                line['data']['nazwakontrahenta'] or 'BRAK'
            )
            etree.SubElement(sale_row, etree.QName(tns, 'DowodSprzedazy')).text = line['data']['dowodsprzedazyzakupu']
            # noinspection PyUnresolvedReferences
            etree.SubElement(sale_row, etree.QName(tns, 'DataWystawienia')).text = line['data'][
                'datawystawienia'
            ].isoformat()

            if (
                line['data']['datasprzedazy']
                and line['data']['datawystawienia']
                and line['data']['datasprzedazy'] != line['data']['datawystawienia']
            ):
                # noinspection PyUnresolvedReferences
                etree.SubElement(sale_row, etree.QName(tns, 'DataSprzedazy')).text = line['data'][
                    'datasprzedazy'
                ].isoformat()

            if line['data']['typdokumentu']:
                etree.SubElement(sale_row, etree.QName(tns, 'TypDokumentu')).text = line['data']['typdokumentu']

            for child in line['children']:
                if child['istax']:
                    section_sum += child['kwota']

                if child['gtu']:
                    _flags.add(child['gtu'])

                if child['jpkgroup']:
                    declaration_groups.setdefault(child['jpkgroup'], 0.0)
                    declaration_groups[child['jpkgroup']] += child['kwota']

                if child['jpkmarkup']:
                    _taxes.add((child['jpkmarkup'], child['kwota']))

            for flag in filter(lambda f: f in _flags, FLAGS):
                etree.SubElement(sale_row, etree.QName(tns, flag)).text = '1'

            for tag, value in sorted(_taxes, key=lambda x: x[0]):
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

            _vat = line['data']['nrkontrahenta']
            _country = None
            _flags = set(line['data']['flags'].split(',')) if line['data']['flags'] else set()
            _taxes = set()

            if line['data']['partnerid']:
                _country = self.env['res.partner'].browse(line['data']['partnerid']).x_get_eu_vat_country()

            if _country:
                etree.SubElement(purchase_row, etree.QName(tns, 'KodKrajuNadaniaTIN')).text = _country

            etree.SubElement(purchase_row, etree.QName(tns, 'NrDostawcy')).text = _vat or 'BRAK'

            etree.SubElement(purchase_row, etree.QName(tns, 'NazwaDostawcy')).text = (
                line['data']['nazwakontrahenta'] or 'BRAK'
            )
            etree.SubElement(purchase_row, etree.QName(tns, 'DowodZakupu')).text = line['data']['dowodsprzedazyzakupu']

            # noinspection PyUnresolvedReferences
            etree.SubElement(purchase_row, etree.QName(tns, 'DataZakupu')).text = line['data']['datazakupu'].isoformat()

            if (
                line['data']['datawplywu']
                and line['data']['datazakupu']
                and line['data']['datawplywu'] != line['data']['datazakupu']
            ):
                # noinspection PyUnresolvedReferences
                etree.SubElement(purchase_row, etree.QName(tns, 'DataWplywu')).text = line['data'][
                    'datawplywu'
                ].isoformat()

            if line['data']['typdokumentu']:
                etree.SubElement(purchase_row, etree.QName(tns, 'DokumentZakupu')).text = line['data']['typdokumentu']

            for child in line['children']:
                if child['istax']:
                    section_sum += child['kwota']

                if child['gtu']:
                    _flags.add(child['gtu'])

                if child['jpkgroup']:
                    declaration_groups.setdefault(child['jpkgroup'], 0.0)
                    declaration_groups[child['jpkgroup']] += child['kwota']

                if child['jpkmarkup']:
                    _taxes.add((child['jpkmarkup'], child['kwota']))

            for flag in filter(lambda f: f in _flags, FLAGS):
                etree.SubElement(purchase_row, etree.QName(tns, flag)).text = '1'

            # for tag, value in sorted(filter(lambda x: not float_is_zero(x[1], 2), _taxes), key=lambda x: x[0]):
            for tag, value in sorted(_taxes, key=lambda x: x[0]):
                etree.SubElement(purchase_row, etree.QName(tns, tag)).text = float_repr(value, 2)

        section = etree.SubElement(ewidencja, etree.QName(tns, 'ZakupCtrl'))
        etree.SubElement(section, etree.QName(tns, 'LiczbaWierszyZakupow')).text = f'{section_count:d}'
        etree.SubElement(section, etree.QName(tns, 'PodatekNaliczony')).text = f'{section_sum:.2f}'

        for tag, amount in declaration_groups.items():
            int_amount = declaration_groups[tag] = int(float_round(amount, 0))
            etree.SubElement(pozycje_szczegolowe, etree.QName(tns, tag.upper())).text = str(int_amount)

        return etree.tostring(jpk, encoding='UTF-8', xml_declaration=True, pretty_print=True), declaration_groups

    def get_xml(self, options):
        return self.get_xml_extended(options)[0]

    def export_xml_vat_ue(self, options):
        report_date = fields.Date.to_date(options['date']['date_from'])

        xml, group_vals_list = self.env['account.report.vat_ue'].get_xml_extended_vat_ue(options)

        vat_ue_report = self.env['jpk.vat.ue'].create(
            {
                'version': '2-0E',
                'year': report_date.year,
                'month': report_date.month,
                'cel_zlozenia': 1,
                'source_xml': base64.b64encode(xml),
                'group_line_ids': [
                    fields.Command.create(
                        {
                            'country_code': val.get('country_code'),
                            'nip': val.get('vat'),
                            'amount': val.get('amount'),
                            'tt': val.get('tt'),
                            'group': group.lower(),
                        }
                    )
                    for group, vals in group_vals_list.items()
                    for val in vals
                ],
            }
        )

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'jpk.vat.ue',
            'views': [[self.env.ref('trilab_jpk_vat.jpk_vat_ue_view_form').id, 'form']],
            'name': 'VAT UE',
            'res_id': vat_ue_report.id,
            'target': 'new',
            'context': {'form_view_initial_mode': 'edit'},
        }

    def export_xml(self, options):
        report_date = fields.Date.to_date(options['date']['date_from'])

        xml, sums = self.get_xml_extended(options)
        sums = {k.lower(): v for k, v in sums.items()}

        v7m_report = self.env['jpk.vat.7m'].create(
            {
                'version': '1-2E',
                'year': report_date.year,
                'month': report_date.month,
                'cel_zlozenia': options.get('cel_zlozenia', 1),
                'document_type_id': self.env.ref('trilab_jpk_base.jpk_v7m_1_2_doc_type').id,
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
            'context': {'form_view_initial_mode': 'edit'},
        }

    # noinspection PyUnusedLocal
    def get_xlsx(self, options, response=None):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet(self._get_report_name()[:31])

        style_definitions = {
            'default': {'font_name': 'Arial', 'font_size': 12, 'font_color': '#666666'},
            'default_col1': {'font_name': 'Arial', 'font_size': 12, 'font_color': '#666666', 'indent': 2},
            'title': {'font_name': 'Arial', 'bold': True, 'bottom': 2},
            'super_col': {'font_name': 'Arial', 'bold': True, 'align': 'center'},
            'level_0': {'font_name': 'Arial', 'bold': True, 'font_size': 13, 'bottom': 6, 'font_color': '#666666'},
            'level_1': {'font_name': 'Arial', 'bold': True, 'font_size': 13, 'bottom': 1, 'font_color': '#666666'},
            'level_2_col1': {'font_name': 'Arial', 'bold': True, 'font_size': 12, 'font_color': '#666666', 'indent': 1},
            'level_2_col1_total': {'font_name': 'Arial', 'bold': True, 'font_size': 12, 'font_color': '#666666'},
            'level_2': {'font_name': 'Arial', 'bold': True, 'font_size': 12, 'font_color': '#666666'},
            'level_3_col1': {'font_name': 'Arial', 'font_size': 12, 'font_color': '#666666', 'indent': 2},
            'level_3_col1_total': {
                'font_name': 'Arial',
                'bold': True,
                'font_size': 12,
                'font_color': '#666666',
                'indent': 1,
            },
            'level_3': {'font_name': 'Arial', 'font_size': 12, 'font_color': '#666666'},
        }

        styles = {}
        for style_name, style_props in style_definitions.items():
            styles[style_name] = workbook.add_format(style_props)
            styles[f'{style_name}_date'] = workbook.add_format({'num_format': 'yyyy-mm-dd', **style_props})

        # Set the first column width to 20
        sheet.set_column(0, 0, 20)

        sheet.set_column(2, 2, 20)
        sheet.set_column(3, 3, 50)
        sheet.set_column(4, 4, 25)
        sheet.set_column(5, 8, 15)

        sheet.set_column(14, 14, 10)

        super_columns = self._get_super_columns(options)
        y_offset = bool(super_columns.get('columns')) and 1 or 0

        sheet.write(y_offset, 0, '', styles['title'])

        x = super_columns.get('x_offset', 0)
        for super_col in super_columns.get('columns', []):
            cell_content = super_col.get('string', '').replace('<br/>', ' ').replace('&nbsp;', ' ')
            x_merge = super_columns.get('merge')
            if x_merge and x_merge > 1:
                sheet.merge_range(0, x, 0, x + (x_merge - 1), cell_content, styles['super_col'])
                x += x_merge
            else:
                sheet.write(0, x, cell_content, styles['super_col'])
                x += 1
        for row in self.get_header(options):
            x = 0
            for column in row:
                colspan = column.get('colspan', 1)
                header_label = column.get('name', '').replace('<br/>', ' ').replace('&nbsp;', ' ')
                if colspan == 1:
                    sheet.write(y_offset, x, header_label, styles['title'])
                else:
                    sheet.merge_range(y_offset, x, y_offset, x + colspan - 1, header_label, styles['title'])
                x += colspan
            y_offset += 1
        ctx = self._set_context(options)
        ctx.update({'no_format': True, 'print_mode': True, 'prefetch_fields': False})
        # deactivating the prefetching saves ~35% on get_lines running time
        # noinspection PyProtectedMember
        lines = self.with_context(ctx)._get_lines(options)

        if options.get('hierarchy'):
            lines = self._create_hierarchy(lines, options)
        if options.get('selected_column'):
            lines = self._sort_lines(lines, options)

        # write all data rows
        for y in range(0, len(lines)):
            level = lines[y].get('level')
            if lines[y].get('caret_options'):
                style = 'level_3'
                col1_style = style
            elif level == 0:
                y_offset += 1
                style = 'level_0'
                col1_style = style
            elif level == 1:
                style = 'level_1'
                col1_style = style
            elif level == 2:
                style = 'level_2'
                col1_style = 'total' in lines[y].get('class', '').split(' ') and 'level_2_col1_total' or 'level_2_col1'
            elif level == 3:
                style = 'level_3'
                col1_style = 'total' in lines[y].get('class', '').split(' ') and 'level_3_col1_total' or 'level_3_col1'
            else:
                style = 'default'
                col1_style = 'default_col1'

            # write the first column, with a specific style to manage the indentation
            cell_type, cell_value = self._get_cell_type_value(lines[y])
            if cell_type == 'date':
                sheet.write_datetime(y + y_offset, 0, cell_value, styles.get(f'{style}_date', styles.get(style)))
            else:
                sheet.write(y + y_offset, 0, cell_value, styles.get(col1_style))

            # write all the remaining cells
            for x in range(1, len(lines[y]['columns']) + 1):
                cell_type, cell_value = self._get_cell_type_value(lines[y]['columns'][x - 1])
                if cell_type == 'date':
                    sheet.write_datetime(
                        y + y_offset,
                        x + lines[y].get('colspan', 1) - 1,
                        cell_value,
                        styles.get(f'{style}_date', styles.get(style)),
                    )
                else:
                    sheet.write(y + y_offset, x + lines[y].get('colspan', 1) - 1, cell_value, styles.get(style))

        workbook.close()
        output.seek(0)
        generated_file = output.read()
        output.close()

        return generated_file

    def print_xlsx_flat(self, options):
        options['x_no_groupby'] = True
        return {
            'type': 'ir_actions_account_report_download',
            'data': {
                'model': self.env.context.get('model'),
                'options': json.dumps(options),
                'output_format': 'xlsx',
                'financial_id': self.env.context.get('id'),
            },
        }

    # noinspection PyUnusedLocal
    @api.model
    def _get_load_more_line(self, options, offset, remaining, progress):
        return {
            'id': 'loadmore_1',
            'offset': offset,
            'progress': progress,
            'remaining': remaining,
            'class': 'o_account_reports_load_more text-center',
            'name': _('Load more... '),
            'columns': [{}],
            'children': [],
        }

    def check_partners_vat(self, options):
        # works only with trilab_pl_partners_sync installed

        params = {
            'jpk_doc_id': self.env.ref('trilab_jpk_base.jpk_v7m_1_2_doc_type').id,
            'journal_types': ('sale', 'purchase'),
            'date_from': options.get('date', {}).get('date_from'),
            'date_to': options.get('date', {}).get('date_to'),
            'company': self.env.company.id,
            'allowed_states': ('posted', 'draft') if options.get('all_entries') else ('posted',),
        }

        self.env.cr.execute(self._get_query(), params)
        partner_ids = self.env['res.partner'].browse({_l['partnerid'] for _l in self.env.cr.dictfetchall()})

        # noinspection PyUnresolvedReferences
        errors = partner_ids.x_pl_check_mf_nip_wl(raise_exception=False, post_change=False)

        # noinspection PyUnresolvedReferences
        wizard_id = self.env['trilab.check.partner'].create(
            {
                'check_ids': [
                    fields.Command.create(
                        {
                            'partner_id': partner_id,
                            'error_type': error.get('error_type'),
                            'error_message': error.get('error_message'),
                        }
                    )
                    for partner_id, error in errors.items()
                ],
                'mode': 'nip',
            }
        )

        action = clean_action(
            action=partner_ids._x_pl_check_action(record_id=wizard_id.id, title=_('MF VAT Validation Results')),
            env=self.env,
        )
        action.setdefault('context', {})
        action['context']['x_hide_buttons'] = True

        return action
