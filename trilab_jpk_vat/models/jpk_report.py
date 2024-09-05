import datetime
import re
from itertools import groupby

from lxml import etree

from odoo import _, api, models, release
from odoo.exceptions import UserError


class JpkReport(models.AbstractModel):
    _inherit = 'account.report'
    _name = 'account.report.jpk_vat'
    _description = 'JPK VAT Report'

    filter_multi_company = True
    filter_date = {'date_from': '', 'date_to': '', 'filter': 'last_month', 'mode': 'range'}
    filter_correction_number = '0'
    filter_all_entries = False

    grouping_columns = [
        'nrkontrahenta',
        'nazwakontrahenta',
        'adreskontrahenta',
        'dowodsprzedazyzakupu',
        'datawystawienia',
        'datasprzedazy',
        'datazakupu',
        'datawplywu',
    ]

    all_columns = grouping_columns + ['jpkmarkup', 'kwota']

    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    def _get_columns_name(self, options):
        columns_header = [
            {'name': 'Sekcja JPK'},
            {'name': '#'},
            {'name': 'NrKontrahenta'},
            {'name': 'NazwaKontrahenta'},
            {'name': 'AdresKontrahenta'},
            {'name': 'DowodSprzedazyZakupu'},
            {'name': 'DataWystawienia'},
            {'name': 'DataSprzedazy'},
            {'name': 'DataZakupu'},
            {'name': 'DataWplywu'},
            {'name': 'JPKMarkup'},
            {'name': 'kwota', 'class': 'number'},
        ]
        return columns_header

    # noinspection PyUnusedLocal
    @api.model
    def _get_lines(self, options, line_id=None):
        context = self.env.context

        # noinspection SqlResolve
        query = """SELECT aat.jpk_section                             AS JPKSection,
       COALESCE(p.vat, 'brak')                     AS NrKontrahenta,
       p.name                                      AS NazwaKontrahenta,
       COALESCE(p.street || ', ', '') || COALESCE(p.zip || ', ', '') || COALESCE(p.city, '') AS AdresKontrahenta,
       (CASE
            WHEN aj.type = 'sale'
                THEN am.name
            ELSE aml.ref
           END)                                    AS DowodSprzedazyZakupu,
       am.invoice_date                             AS DataWystawienia,
       am.pl_vat_date                              AS DataSprzedazy,
       am.invoice_date                             AS DataZakupu,
       am.pl_vat_date                              AS DataWplywu,
       (CASE
            WHEN aml.tax_line_id IS NOT NULL
                then TRUE
            ELSE FALSE
           END)                                    AS isTax,
       aat.jpk_markup                              AS JPKMarkup,
       SUM(CASE
            WHEN aml.tax_line_id IS NOT NULL and aat.jpk_section='ZakupWiersz'
                then aml.balance
            WHEN aml.tax_line_id IS NOT NULL and aat.jpk_section='SprzedazWiersz'
                then - aml.balance
            WHEN aat.jpk_section='SprzedazWiersz' and am.move_type in ('out_invoice', 'out_refund')
                then  - aml.balance
           ELSE (aml.balance)
           END)                                    AS kwota
FROM account_move AS am
         LEFT JOIN res_partner p ON am.partner_id = p.id
         LEFT JOIN account_journal aj ON am.journal_id = aj.id
         LEFT JOIN account_move_line aml ON aml.move_id = am.id
         LEFT JOIN account_account_tag_account_move_line_rel aatmr ON aatmr.account_move_line_id = aml.id
         LEFT JOIN account_account_tag aat ON aat.id = aatmr.account_account_tag_id
         LEFT JOIN jpk_document_type dt ON dt.id = aat.jpk_document_type
         LEFT JOIN account_tax tax ON tax.id = aml.tax_line_id
WHERE dt.name = 'JPK_VAT'
 AND (tax.tax_exigibility != 'on_payment'
        OR am.tax_cash_basis_rec_id IS NOT NULL
        OR am.always_tax_exigible = TRUE) = TRUE
 AND aj.type IN %s
 AND am.pl_vat_date >= %s
 AND am.pl_vat_date <= %s
 AND am.company_id = %s
GROUP BY am.id, JPKSection, NrKontrahenta, NazwaKontrahenta, AdresKontrahenta, DowodSprzedazyZakupu, DataWystawienia,
         isTax, JPKMarkup
ORDER BY JPKsection, DataWystawienia, DowodSprzedazyZakupu, JPKMarkup"""

        # params = (('sale', 'purchase'), context.get('pl_vat_date_from'), context.get('pl_vat_date_to'),
        #           self.env.company.id)
        params = (('sale', 'purchase'), context.get('date_from'), context.get('date_to'), self.env.company.id)
        self.env.cr.execute(query, params)

        dict_output = context.get('dict_output', False)

        if dict_output:
            lines = {}
        else:
            lines = []

        for jpk_section, group in groupby(self.env.cr.dictfetchall(), lambda x: x['jpksection']):
            section = []
            counter = 1

            for sk, sub_group in groupby(group, lambda x: [x[k] for k in self.grouping_columns]):
                if context.get('print_mode', False):
                    # e.g. excel output
                    for counter, row in enumerate(sub_group):
                        # noinspection PyTypeChecker
                        lines.append(
                            {
                                'id': f"{jpk_section}:{counter}:{row['jpkmarkup']}",
                                # 'caret_options': 'account.move.line',
                                'model': 'account.move.line',
                                # 'depth': 1,
                                'name': row['jpksection'],
                                # 'parent_id': master_line['id'],
                                'columns': [{}] + [{'name': row[k]} for k in self.all_columns],
                                'unfoldable': False,
                                'unfolded': False,
                                'isTax': row['istax'],
                            }
                        )
                else:
                    master_line = None

                    for row in sub_group:
                        # update dates for rows
                        if jpk_section == 'SprzedazWiersz':
                            row['datawplywu'] = row['datazakupu'] = None
                        elif jpk_section == 'ZakupWiersz':
                            row['datasprzedazy'] = row['datawystawienia'] = None

                        if not master_line:
                            if dict_output:
                                master_line = {'data': row, 'counter': counter, 'children': []}
                            else:
                                # noinspection PyTypeChecker
                                master_line = {
                                    'id': 'hierarchy',
                                    # 'parent_id': f'{jpk_section}:{counter}',
                                    # 'caret_options': 'account.move.line',
                                    'model': 'account.move.line',
                                    'name': jpk_section,
                                    'level': 1,
                                    'columns': [{'name': counter}]
                                    + [{'name': row[k]} for k in self.grouping_columns]
                                    + [{}, {}],
                                    'unfoldable': False,
                                    'unfolded': True,
                                    'children': [],
                                }

                        if dict_output:
                            master_line['children'].append(row)
                        else:
                            # noinspection PyTypeChecker
                            master_line['children'].append(
                                {
                                    'id': f"{jpk_section}:{counter}:{row['jpkmarkup']}",
                                    # 'caret_options': 'account.move.line',
                                    # 'model': 'account.move.line',
                                    'depth': 1,
                                    # 'name': row['jpkmarkup'],
                                    'parent_id': master_line['id'],
                                    'columns': [{}] * (len(self.grouping_columns) + 1)
                                    + [{'name': row['jpkmarkup']}, {'name': row['kwota']}],
                                    'unfoldable': False,
                                    'unfolded': False,
                                    'isTax': row['istax'],
                                }
                            )

                    section.append(master_line)
                    counter += 1

            if not context.get('print_mode', False):
                if dict_output:
                    lines[jpk_section] = section
                else:
                    for master in section:
                        children = master.pop('children')
                        lines.append(master)
                        lines.extend(children)

        return lines

    @api.model
    def _create_hierarchy(self, lines):
        return lines

    @api.model
    def _get_report_name(self):
        return _('Jednolity Plik Kontrolny - VAT')

    def _get_reports_buttons(self, options):
        buttons = [
            {'name': _('Export (XLSX)'), 'sequence': 1, 'action': 'print_xlsx'},
            {'name': _('Export XML'), 'sequence': 2, 'action': 'print_xml'},
        ]

        module = self.env['ir.module.module'].sudo().search([['name', '=', 'trilab_jpk_transfer']])

        if module and module.state == 'installed':
            buttons.append({'name': _('Export XML and send'), 'sequence': 3, 'action': 'transfer_xml'})

        return buttons

    def get_html(self, options, line_id=None, additional_context=None):
        return super(JpkReport, self).get_html(options, line_id, additional_context)

    # noinspection PyTypeChecker
    def get_xml(self, options):
        # noinspection HttpUrlsUsage
        tns = 'http://jpk.mf.gov.pl/wzor/2017/11/13/1113/'
        jpk = etree.Element(etree.QName(tns, 'JPK'), nsmap={'tns': tns})
        header = etree.SubElement(jpk, etree.QName(tns, 'Naglowek'))

        etree.SubElement(
            header, etree.QName(tns, 'KodFormularza'), attrib={'kodSystemowy': 'JPK_VAT (3)', 'wersjaSchemy': '1-1'}
        ).text = 'JPK_VAT'
        etree.SubElement(header, etree.QName(tns, 'WariantFormularza')).text = '3'
        etree.SubElement(header, etree.QName(tns, 'CelZlozenia')).text = f"{options.get('correction_number', 0)}"
        etree.SubElement(header, etree.QName(tns, 'DataWytworzeniaJPK')).text = datetime.datetime.now().isoformat()
        etree.SubElement(header, etree.QName(tns, 'DataOd')).text = options['date']['date_from']
        etree.SubElement(header, etree.QName(tns, 'DataDo')).text = options['date']['date_to']
        etree.SubElement(header, etree.QName(tns, 'NazwaSystemu')).text = f'{release.description} {release.version}'

        company = self.env.company
        podmiot = etree.SubElement(jpk, etree.QName(tns, 'Podmiot1'))
        try:
            etree.SubElement(podmiot, etree.QName(tns, 'NIP')).text = re.sub(r'\D', '', company.vat)
        except TypeError:
            raise UserError(_("Make sure that Company's VAT number is correct"))

        etree.SubElement(podmiot, etree.QName(tns, 'PelnaNazwa')).text = company.name
        etree.SubElement(podmiot, etree.QName(tns, 'Email')).text = company.x_get_jpk_email()

        ctx = self._set_context(options)

        # deactivating the prefetching saves ~35% on get_lines running time
        ctx.update({'no_format': True, 'print_mode': False, 'prefetch_fields': False, 'dict_output': True})
        # noinspection PyProtectedMember
        sections = self.with_context(ctx)._get_lines(options)

        # SprzedazWiersz
        section_count = 0
        section_sum = 0.0

        for line in sections.get('SprzedazWiersz', []):
            section_count += 1
            sale_row = etree.SubElement(jpk, etree.QName(tns, 'SprzedazWiersz'))
            etree.SubElement(sale_row, etree.QName(tns, 'LpSprzedazy')).text = str(line['counter'])
            etree.SubElement(sale_row, etree.QName(tns, 'NrKontrahenta')).text = line['data']['nrkontrahenta']
            etree.SubElement(sale_row, etree.QName(tns, 'NazwaKontrahenta')).text = line['data']['nazwakontrahenta']
            etree.SubElement(sale_row, etree.QName(tns, 'AdresKontrahenta')).text = line['data']['adreskontrahenta']
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

            for child in line['children']:
                if child['istax']:
                    section_sum += child['kwota']
                etree.SubElement(sale_row, etree.QName(tns, child['jpkmarkup'])).text = f"{child['kwota']:.2f}"

        section = etree.SubElement(jpk, etree.QName(tns, 'SprzedazCtrl'))
        etree.SubElement(section, etree.QName(tns, 'LiczbaWierszySprzedazy')).text = f'{section_count:d}'
        etree.SubElement(section, etree.QName(tns, 'PodatekNalezny')).text = f'{section_sum:.2f}'

        # ZakupWiersz
        section_count = 0
        section_sum = 0.0

        for line in sections.get('ZakupWiersz', []):
            section_count += 1
            purchase_row = etree.SubElement(jpk, etree.QName(tns, 'ZakupWiersz'))
            etree.SubElement(purchase_row, etree.QName(tns, 'LpZakupu')).text = str(line['counter'])
            etree.SubElement(purchase_row, etree.QName(tns, 'NrDostawcy')).text = line['data']['nrkontrahenta']
            etree.SubElement(purchase_row, etree.QName(tns, 'NazwaDostawcy')).text = line['data']['nazwakontrahenta']
            etree.SubElement(purchase_row, etree.QName(tns, 'AdresDostawcy')).text = line['data']['adreskontrahenta']
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

            for child in line['children']:
                if child['istax']:
                    section_sum += child['kwota']
                etree.SubElement(purchase_row, etree.QName(tns, child['jpkmarkup'])).text = f"{child['kwota']:.2f}"

        section = etree.SubElement(jpk, etree.QName(tns, 'ZakupCtrl'))
        etree.SubElement(section, etree.QName(tns, 'LiczbaWierszyZakupow')).text = f'{section_count:d}'
        etree.SubElement(section, etree.QName(tns, 'PodatekNaliczony')).text = f'{section_sum:.2f}'

        return etree.tostring(jpk, encoding='UTF-8', xml_declaration=True, pretty_print=True)

    def transfer_xml(self, options):
        date = options.get('date', {}).get('string', '')

        # noinspection PyUnresolvedReferences
        transfer_id = self.env['jpk.transfer'].create_with_document(
            {
                'name': f'JPK VAT {date}',
                'jpk_type': 'JPK',
                'file_name': f'jpk_vat_{date}.xml',
                'data': self.get_xml(options),
                'document_type': 'trilab_jpk_base.jpk_vat_doc_type',
            }
        )

        # noinspection PyUnresolvedReferences
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'jpk.transfer',
            'views': [[False, 'form']],
            'res_id': transfer_id.id,
            # 'target': 'new'
        }
