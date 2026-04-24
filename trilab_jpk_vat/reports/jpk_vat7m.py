import datetime
import re
from collections import namedtuple
from types import SimpleNamespace

from lxml import etree
from odoo import _, api, models, release
from odoo.addons.trilab_jpk_base.models.export_helper import CellDefinition
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

TagDef = namedtuple('str', ('tag', 'key'))


class JpkVat7MReport(models.AbstractModel):
    _name = 'report.trilab_jpk_vat.jpk_vat7m_report'
    _inherit = ['jpk.trilab.export_helper']
    _description = 'VAT 7M'

    # noinspection PyArgumentList
    grouping_columns = [
        CellDefinition('jpksection', 'Sekcja JPK', width=20),
        CellDefinition(None, 'Lp'),
        CellDefinition('nrkontrahenta', 'Nr kontrahenta'),
        CellDefinition('nazwakontrahenta', 'Nazwa kontrahenta'),
        CellDefinition('dowodsprzedazyzakupu', 'Nr dokumentu'),
        CellDefinition('datawystawienia', 'Data wystawienia', 'date'),
        CellDefinition('datasprzedazy', 'Data sprzedaży', 'date'),
        CellDefinition('datazakupu', 'Data zakupu', 'date'),
        CellDefinition('datawplywu', 'Data wpływu', 'date'),
        CellDefinition('terminplatnosci', 'Termin płatności', 'date'),
        CellDefinition('typdokumentu', 'Typ dokumentu'),
        CellDefinition('flags', 'Flagi'),
    ]

    # noinspection PyArgumentList
    detail_columns = [
        CellDefinition('flags', 'Znaczniki'),
        CellDefinition('gtu', 'GTU'),
        CellDefinition('istax', 'Podatek'),
        CellDefinition('jpkmarkup', 'Kod JPK'),
        CellDefinition('jpkgroup', 'Grupa JPK'),
        CellDefinition('kwota', 'Kwota'),
    ]

    columns = grouping_columns + detail_columns

    xlsx_styles = {
        'default': {'font_name': 'Arial', 'font_size': 12, 'font_color': '#666666'},
        'title': {'font_name': 'Arial', 'bold': True, 'bottom': 2},
        #     'default_col1': {'font_name': 'Arial', 'font_size': 12, 'font_color': '#666666', 'indent': 2},
        #     'super_col': {'font_name': 'Arial', 'bold': True, 'align': 'center'},
        #     'level_0': {'font_name': 'Arial', 'bold': True, 'font_size': 13, 'bottom': 6, 'font_color': '#666666'},
        #     'level_1': {'font_name': 'Arial', 'bold': True, 'font_size': 13, 'bottom': 1, 'font_color': '#666666'},
        #     'level_2_col1': {'font_name': 'Arial', 'bold': True, 'font_size': 12, 'font_color': '#666666',
        #     'indent': 1},
        #     'level_2_col1_total': {'font_name': 'Arial', 'bold': True, 'font_size': 12, 'font_color': '#666666'},
        #     'level_2': {'font_name': 'Arial', 'bold': True, 'font_size': 12, 'font_color': '#666666'},
        #     'level_3_col1': {'font_name': 'Arial', 'font_size': 12, 'font_color': '#666666', 'indent': 2},
        #     'level_3_col1_total': {
        #         'font_name': 'Arial',
        #         'bold': True,
        #         'font_size': 12,
        #         'font_color': '#666666',
        #         'indent': 1,
        #     },
        #     'level_3': {'font_name': 'Arial', 'font_size': 12, 'font_color': '#666666'},
        # }
    }

    @staticmethod
    def _get_purchase_sale_mapping():
        sale_mapping = {
            'row': TagDef('SprzedazWiersz', None),
            'counter': TagDef('LpSprzedazy', None),
            'vat': TagDef('NrKontrahenta', 'nrkontrahenta'),
            'partner_name': TagDef('NazwaKontrahenta', 'nazwakontrahenta'),
            'country': TagDef('KodKrajuNadaniaTIN', None),
            'receipt': TagDef('DowodSprzedazy', 'dowodsprzedazyzakupu'),
            'receipt_date': TagDef('DataWystawienia', 'datawystawienia'),
            'transaction_date': TagDef('DataSprzedazy', 'datasprzedazy'),
            'doc_type': TagDef('TypDokumentu', 'typdokumentu'),
            'ctrl': TagDef('SprzedazCtrl', None),
            'ctrl_count': TagDef('LiczbaWierszySprzedazy', None),
            'ctrl_tax': TagDef('PodatekNalezny', None),
        }

        purchase_mapping = {
            'row': TagDef('ZakupWiersz', None),
            'counter': TagDef('LpZakupu', None),
            'vat': TagDef('NrDostawcy', 'nrkontrahenta'),
            'partner_name': TagDef('NazwaDostawcy', 'nazwakontrahenta'),
            'country': TagDef('KodKrajuNadaniaTIN', None),
            'receipt': TagDef('DowodZakupu', 'dowodsprzedazyzakupu'),
            'receipt_date': TagDef('DataZakupu', 'datazakupu'),
            'transaction_date': TagDef('DataWplywu', 'datawplywu'),
            'doc_type': TagDef('TypDokumentu', 'typdokumentu'),
            'ctrl': TagDef('ZakupCtrl', None),
            'ctrl_count': TagDef('LiczbaWierszyZakupow', None),
            'ctrl_tax': TagDef('PodatekNaliczony', None),
        }

        assert sale_mapping.keys() == purchase_mapping.keys()

        return SimpleNamespace(**sale_mapping), SimpleNamespace(**purchase_mapping)

    @staticmethod
    def _get_query():
        return """SELECT am.id                         AS gid,
               jat.jpk_section                             AS JPKSection,
               p.vat                                       AS NrKontrahenta,
               p.name                                      AS NazwaKontrahenta,
               p.id                                        AS PartnerId,
               (CASE
                    WHEN am.x_pl_change_jpk_proof IS NOT NULL
                        THEN am.x_pl_change_jpk_proof
                    WHEN aj.type = 'sale'
                        THEN am.name
                    ELSE aml.ref
                   END)                                    AS DowodSprzedazyZakupu,
               coalesce (am.invoice_date, am.date)         AS DataWystawienia,
               am.x_invoice_sale_date                      AS DataSprzedazy,
               am.invoice_date                             AS DataZakupu,
               am.pl_vat_date                              AS DataWplywu,
               (CASE
                    WHEN aml.tax_line_id IS NOT NULL
                        then TRUE
                    ELSE FALSE
                END)                                       AS isTax,
               jat.jpk_markup                              AS JPKMarkup,
               jat.jpk_v7_group                            AS JPKGroup,
                (CASE
                    WHEN jat.jpk_section='SprzedazWiersz'
                        THEN am.x_pl_vat_typ_dokumentu
                    ELSE am.x_pl_vat_dokument_zakupu
                END)                                       AS TypDokumentu,
               (CASE 
                   WHEN jat.jpk_section = 'SprzedazWiersz' 
                   THEN STRING_AGG(DISTINCT jpk_gtu.name, ',')
                END)                                       AS GTU,
               CONCAT_WS(',', CASE WHEN am.x_pl_vat_tp AND jat.jpk_section = 'SprzedazWiersz' THEN 'TP' END,
                              CASE WHEN am.x_pl_vat_tt_wnt AND jat.jpk_section = 'SprzedazWiersz' THEN 'TT_WNT' END,
                              CASE WHEN am.x_pl_vat_tt_d THEN 'TT_D' END,
                              CASE WHEN am.x_pl_vat_mr_t THEN 'MR_T' END,
                              CASE WHEN am.x_pl_vat_mr_uz THEN 'MR_UZ' END,
                              CASE WHEN am.x_pl_vat_i42 THEN 'I_42' END,
                              CASE WHEN am.x_pl_vat_i63 THEN 'I_63' END,
                              CASE WHEN am.x_pl_vat_b_spv THEN 'B_SPV' END,
                              CASE WHEN am.x_pl_vat_b_spv_dostawa THEN 'B_SPV_DOSTAWA' END,
                              CASE WHEN am.x_pl_vat_b_mpv_prowizja THEN 'B_MPV_PROWIZJA' END,
                              CASE WHEN am.x_pl_vat_korekta_podstawy_opodt AND jat.jpk_section='SprzedazWiersz'
                                   THEN 'KorektaPodstawyOpodt' END,
                              CASE WHEN am.x_pl_vat_imp AND jat.jpk_section='ZakupWiersz' THEN 'IMP' END,
                              CASE WHEN am.x_pl_vat_wsto_ee THEN 'WSTO_EE' END,
                              CASE WHEN am.x_pl_vat_ied THEN 'IED' END
                            )                              AS Flags,
               SUM(CASE
                    WHEN aml.tax_line_id IS NOT NULL AND jat.jpk_section='ZakupWiersz'
                        then aml.balance
                    WHEN aml.tax_line_id IS NOT NULL AND jat.jpk_section='SprzedazWiersz'
                        then - aml.balance
                    WHEN jat.jpk_section='SprzedazWiersz' AND am.move_type in ('out_invoice', 'out_refund', 'entry')
                        then  - aml.balance
                   ELSE (aml.balance)
                   END)                                    AS kwota,
                   am.invoice_date_due AS TerminPlatnosci
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
         AND aml.display_type != ANY ('{"line_section", "line_note"}')
        GROUP BY am.id, JPKSection, NrKontrahenta, NazwaKontrahenta, PartnerId, DowodSprzedazyZakupu, DataWystawienia,
                 DataSprzedazy, DataZakupu, DataWplywu, isTax, TypDokumentu, Flags, JPKMarkup, JPKGroup, TerminPlatnosci
        ORDER BY JPKsection, DataWystawienia, am.id, DowodSprzedazyZakupu, JPKMarkup, JPKGroup"""

    # noinspection PyUnusedLocal
    @api.model
    def _get_report_data(self, docids, options):
        context = self.env.context
        query = self._get_query()

        params = {
            'jpk_doc_id': self.env.ref('trilab_jpk_base.jpk_v7m_1_2_doc_type').id,
            'journal_types': ('sale', 'purchase'),
            'date_from': options.get('date_from'),
            'date_to': options.get('date_to'),
            'company': options.get('company_id'),
            'allowed_states': ('posted',) if options.get('only_posted_moves') else ('posted', 'draft'),
        }

        self.env.cr.execute(query, params)

        lines = {'SprzedazWiersz': [], 'ZakupWiersz': []}

        section_counter = options.get('lines_remaining', {})
        master_line = False
        jpk_section = 'BRAK'
        gid = None
        lines_offset = 0
        child_fields = [fld.field for fld in self.detail_columns]

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

            if not master_line:
                lines[jpk_section].append(
                    {
                        'data': {_key: _value for _key, _value in row.items() if _key not in child_fields},
                        'counter': section_counter[jpk_section],
                        'children': [],
                    }
                )
                master_line = True

            lines[jpk_section][-1]['children'].append({_key: row[_key] for _key in child_fields})

        return lines

    def _get_report_values(self, docids, data):
        company = self.env['res.company'].browse(data['company_id'])

        vat_report = self._get_report_data(docids=docids, options=data)

        return {
            'company_name': company.display_name,
            'currency_name': company.currency_id.name,
            'date_to': data['date_to'],
            'date_from': data['date_from'],
            'doc': vat_report,
        }

    @api.model
    def _get_report_name(self):
        return _('Jednolity Plik Kontrolny - VAT7M')

    def generate_xlsx_report(self, workbook, doc_ids, options):
        # self.generate_xlsx_styles(workbook)
        data = self._get_report_data(doc_ids, options)
        sheet = workbook.add_worksheet(self._get_report_name()[:31])

        # Set the first column width to 20
        sheet.set_column(0, 0, 20)
        sheet.set_column(2, 2, 20)
        sheet.set_column(3, 3, 50)
        sheet.set_column(4, 4, 25)
        sheet.set_column(5, 8, 15)
        sheet.set_column(14, 14, 10)

        y_offset = 0

        for col_idx, field in enumerate(self.columns):
            self._write_cell(sheet, y_offset, col_idx, field.name, style='header')

        y_offset += 1

        def process_section(lines):
            nonlocal y_offset
            for row_idx, line in enumerate(lines, start=1):
                for c_idx, field_def in enumerate(self.grouping_columns):
                    if not field_def.field:
                        value = row_idx
                    else:
                        value = line['data'].get(field_def.field)

                    self._write_cell(sheet, y_offset, c_idx, value, definition=field_def)

                y_offset += 1

                for sub_line in line.get('children'):
                    for c_idx, field_def in enumerate(self.detail_columns, start=len(self.grouping_columns)):
                        self._write_cell(sheet, y_offset, c_idx, sub_line.get(field_def.field), definition=field_def)

                    y_offset += 1

        def process_section_flat(lines):
            nonlocal y_offset
            for row_idx, line in enumerate(lines, start=1):
                for sub_line in line.get('children'):
                    for c_idx, field_def in enumerate(self.grouping_columns):
                        if not field_def.field:
                            value = row_idx
                        else:
                            value = line['data'].get(field_def.field)

                        self._write_cell(sheet, y_offset, c_idx, value, definition=field_def)

                    for c_idx, field_def in enumerate(self.detail_columns, start=len(self.grouping_columns)):
                        self._write_cell(sheet, y_offset, c_idx, sub_line.get(field_def.field), definition=field_def)

                    y_offset += 1

        processing_fn = process_section_flat if self.env.context.get('x_flat') else process_section

        processing_fn(data.get('SprzedazWiersz', []))

        if not self.env.context.get('x_flat'):
            y_offset += 1

        processing_fn(data.get('ZakupWiersz', []))

    def get_xml_extended(self, options):
        # noinspection HttpUrlsUsage
        tns = 'http://crd.gov.pl/wzor/2020/05/08/9393/'
        # noinspection HttpUrlsUsage
        tns_etd = 'http://crd.gov.pl/xml/schematy/dziedzinowe/mf/2016/01/25/eD/DefinicjeTypy/'

        company_id = self.env['res.company'].browse(options.get('company_id', self.env.company.id))

        jpk = etree.Element(etree.QName(tns, 'JPK'), nsmap={'tns': tns, 'etd': tns_etd})
        header = etree.SubElement(jpk, etree.QName(tns, 'Naglowek'))

        etree.SubElement(
            header, etree.QName(tns, 'KodFormularza'), attrib={'kodSystemowy': 'JPK_V7M (1)', 'wersjaSchemy': '1-2E'}
        ).text = 'JPK_VAT'
        etree.SubElement(header, etree.QName(tns, 'WariantFormularza')).text = '1'
        etree.SubElement(header, etree.QName(tns, 'DataWytworzeniaJPK')).text = datetime.datetime.now().isoformat()
        etree.SubElement(header, etree.QName(tns, 'NazwaSystemu')).text = f'{release.description} {release.version}'

        etree.SubElement(
            header, etree.QName(tns, 'CelZlozenia'), attrib={'poz': 'P_7'}
        ).text = f'{options.get("submit_purpose", 1)}'

        if not company_id.pl_tax_office_id.code:
            raise UserError(_('PL Tax Office is not set for company %s', company_id.name))

        etree.SubElement(header, etree.QName(tns, 'KodUrzedu')).text = company_id.pl_tax_office_id.code

        etree.SubElement(header, etree.QName(tns, 'Rok')).text = str(options['date_from'].year)
        etree.SubElement(header, etree.QName(tns, 'Miesiac')).text = str(options['date_from'].month)

        podmiot = etree.SubElement(jpk, etree.QName(tns, 'Podmiot1'), attrib={'rola': 'Podatnik'})

        # UWAGA tylko dla osób niefizycznych!
        # podmiot_sub = etree.SubElement(jpk, etree.QName(tns, 'OsobaFizyczna'))
        podmiot_sub = etree.SubElement(podmiot, etree.QName(tns, 'OsobaNiefizyczna'))

        try:
            etree.SubElement(podmiot_sub, etree.QName(tns, 'NIP')).text = re.sub(r'\D', '', company_id.vat)
        except TypeError:
            raise UserError(_("Make sure that Company's VAT number is correct"))

        # noinspection PyUnreachableCode
        if False:  # osoba fizyczna todo dodać warunek
            _parts = company_id.name.split()
            etree.SubElement(podmiot_sub, etree.QName(tns, 'ImiePierwsze')).text = _parts[0]
            etree.SubElement(podmiot_sub, etree.QName(tns, 'Nazwisko')).text = ' '.join(_parts[1:]) if _parts else ''
            etree.SubElement(podmiot_sub, etree.QName(tns, 'DataUrodzenia')).text = None  # todo skąd wziąć?
        else:  # osoba niefizyczna
            etree.SubElement(podmiot_sub, etree.QName(tns, 'PelnaNazwa')).text = company_id.name

        # common
        etree.SubElement(podmiot_sub, etree.QName(tns, 'Email')).text = company_id.x_get_jpk_email()

        if company_id.phone:
            etree.SubElement(podmiot_sub, etree.QName(tns, 'Telefon')).text = company_id.phone

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

        # deactivating the prefetching saves ~35% on get_lines running time
        ctx = {'no_format': True, 'print_mode': False, 'prefetch_fields': False, 'dict_output': True}
        sections = self.with_context(**ctx)._get_report_data(docids=None, options=options)

        declaration_groups = {}

        for mapping in self._get_purchase_sale_mapping():
            section_count = 0
            section_sum = 0.0

            for line in sections.get(mapping.row.tag, []):
                section_count += 1
                row = etree.SubElement(ewidencja, etree.QName(tns, mapping.row.tag))
                etree.SubElement(row, etree.QName(tns, mapping.counter.tag)).text = str(line['counter'])

                _vat = line['data'][mapping.vat.key]
                _country = None
                _taxes = set()
                _flags = set()

                if line['data']['partnerid']:
                    _country = self.env['res.partner'].browse(line['data']['partnerid']).x_get_eu_vat_country()

                if _country:
                    etree.SubElement(row, etree.QName(tns, mapping.country.tag)).text = _country

                etree.SubElement(row, etree.QName(tns, mapping.vat.tag)).text = _vat or 'BRAK'
                etree.SubElement(row, etree.QName(tns, mapping.partner_name.tag)).text = (
                    line['data'][mapping.partner_name.key] or 'BRAK'
                )
                etree.SubElement(row, etree.QName(tns, mapping.receipt.tag)).text = line['data'][mapping.receipt.key]

                # noinspection PyUnresolvedReferences
                etree.SubElement(row, etree.QName(tns, mapping.receipt_date.tag)).text = line['data'][
                    mapping.receipt_date.key
                ].isoformat()

                transaction_date = line['data'][mapping.transaction_date.key]
                receipt_date = line['data'][mapping.receipt_date.key]

                if transaction_date and receipt_date and transaction_date != receipt_date:
                    # noinspection PyUnresolvedReferences
                    etree.SubElement(
                        row, etree.QName(tns, mapping.transaction_date.tag)
                    ).text = transaction_date.isoformat()

                if line['data'][mapping.doc_type.key]:
                    etree.SubElement(row, etree.QName(tns, mapping.doc_type.tag)).text = line['data'][
                        mapping.doc_type.key
                    ]

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
                    etree.SubElement(row, etree.QName(tns, flag)).text = '1'

                for tag, value in sorted(_taxes, key=lambda x: x[0]):
                    etree.SubElement(row, etree.QName(tns, tag)).text = float_repr(value, 2)

            section = etree.SubElement(ewidencja, etree.QName(tns, mapping.ctrl.tag))
            etree.SubElement(section, etree.QName(tns, mapping.ctrl_count.tag)).text = f'{section_count:d}'
            etree.SubElement(section, etree.QName(tns, mapping.ctrl_tax.tag)).text = f'{section_sum:.2f}'

        for tag, amount in declaration_groups.items():
            int_amount = declaration_groups[tag] = int(float_round(amount, 0))
            etree.SubElement(pozycje_szczegolowe, etree.QName(tns, tag.upper())).text = str(int_amount)

        return etree.tostring(jpk, encoding='UTF-8', xml_declaration=True, pretty_print=True), declaration_groups

    def generate_xml_report(self, file_data, doc_ids, options):
        if doc_ids:
            file_data.write(self.env['jpk.vat.7m'].browse(doc_ids).get_xml(options))

        else:
            file_data.write(self.get_xml_extended(options)[0])
