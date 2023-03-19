import re

from lxml import etree

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_round


class VatUeReport(models.AbstractModel):
    _inherit = 'account.report'
    _name = 'account.report.vat_ue'
    _description = 'VAT UE Report'

    GROUP_MAPPING = {
        'group1': {'name': 'Grupa1', 'prefix': 'D'},
        'group2': {'name': 'Grupa2', 'prefix': 'N'},
        'group3': {'name': 'Grupa3', 'prefix': 'U'},
        'group4': {'name': 'Grupa4', 'prefix': 'C'},
    }

    @api.model
    def _get_lines_vat_ue(self, options):
        context = self.env.context
        query = self._get_query_vat_ue()

        account_tags = (
            self.env.ref('trilab_jpk_vat.pl_jpk_K_21').id,
            self.env.ref('trilab_jpk_vat.pl_jpk_K_23').id,
            self.env.ref('trilab_jpk_vat.pl_jpk_K_12').id,
        )

        if not all(account_tags):
            return False

        params = {
            'jpk_doc_id': self.env.ref('trilab_jpk_base.vat_ue5_v2_0e_doc_type').id,
            'journal_types': ('sale', 'purchase'),
            'date_from': context.get('date_from'),
            'date_to': context.get('date_to'),
            'company': self.env.company.id,
            'allowed_states': ('posted', 'draft') if options.get('all_entries') else ('posted',),
            'account_tags': account_tags,
        }

        self.env.cr.execute(query, params)

        lines = {'group1': [], 'group2': [], 'group3': [], 'group4': []}

        for row in self.env.cr.dictfetchall():
            if row['jpkgroup']:
                lines[row['jpkgroup']].append(row)

        return lines

    def get_xml_extended_vat_ue(self, options):
        company = self.env.company
        if not (company.pl_tax_office_id and company.pl_tax_office_id.code):
            raise UserError(_('PL Tax Office is not set for company %s', company.name))

        # noinspection HttpUrlsUsage
        tns = 'http://crd.gov.pl/wzor/2021/01/12/10293/'
        # noinspection HttpUrlsUsage
        tns_etd = 'http://crd.gov.pl/xml/schematy/dziedzinowe/mf/2020/03/11/eD/DefinicjeTypy/'

        deklaracja = etree.Element(etree.QName('Deklaracja'), nsmap={None: tns, 'etd': tns_etd})
        header = etree.SubElement(deklaracja, etree.QName('Naglowek'))

        etree.SubElement(
            header, etree.QName('KodFormularza'), attrib={'kodSystemowy': 'VAT-UE (5)', 'wersjaSchemy': '2-0E'}
        ).text = 'VAT-UE'
        etree.SubElement(header, etree.QName('WariantFormularza')).text = '5'

        report_date = fields.Date.to_date(options['date']['date_from'])
        etree.SubElement(header, etree.QName('Rok')).text = str(report_date.year)
        etree.SubElement(header, etree.QName('Miesiac')).text = str(report_date.month)

        etree.SubElement(header, etree.QName('CelZlozenia')).text = f'{options.get("cel_zlozenia", 1)}'
        etree.SubElement(header, etree.QName('KodUrzedu')).text = company.pl_tax_office_id.code

        podmiot = etree.SubElement(deklaracja, etree.QName('Podmiot1'), attrib={'rola': 'Podatnik'})

        # UWAGA tylko dla osób niefizycznych!
        # podmiot_sub = etree.SubElement(jpk, etree.QName(tns_etd, 'OsobaFizyczna'))
        podmiot_sub = etree.SubElement(podmiot, etree.QName(tns_etd, 'OsobaNiefizyczna'))

        try:
            etree.SubElement(podmiot_sub, etree.QName(tns_etd, 'NIP')).text = re.sub(r'\D', '', company.vat)
        except TypeError:
            raise UserError(_("Make sure that Company's VAT number is correct"))

        etree.SubElement(podmiot_sub, etree.QName(tns_etd, 'PelnaNazwa')).text = company.name

        pozycje_szczegolowe = etree.SubElement(deklaracja, etree.QName('PozycjeSzczegolowe'))
        etree.SubElement(deklaracja, etree.QName('Pouczenie')).text = '1'

        group_vals_list = {'group1': [], 'group2': [], 'group3': [], 'group4': []}

        ctx = self._set_context(options)

        # deactivating the prefetching saves ~35% on get_lines running time
        ctx.update({'no_format': True, 'print_mode': False, 'prefetch_fields': False, 'dict_output': True})
        # noinspection PyProtectedMember
        groups = self.with_context(ctx)._get_lines_vat_ue(options)

        if groups:
            for group in ['group1', 'group2', 'group3', 'group4']:
                for line in groups.get(group, []):
                    sale_row = etree.SubElement(
                        pozycje_szczegolowe, etree.QName(self.GROUP_MAPPING[group]['name'])
                    )

                    group_vals = {}
                    _partner = self.env['res.partner'].browse(line['partnerid'])

                    _vat = _partner.x_get_eu_vat()
                    _country = _partner.x_get_eu_vat_country()

                    _flags = set(line['flags'].split(',')) if line['flags'] else set()
                    _taxes = set()

                    group_vals['country_code'] = _country

                    prefix = self.GROUP_MAPPING[group]['prefix']

                    etree.SubElement(sale_row, etree.QName(f'P_{prefix}a')).text = _country

                    etree.SubElement(sale_row, etree.QName(f'P_{prefix}b')).text = _vat and _vat[2:] or 'BRAK'
                    group_vals['vat'] = _vat and _vat[2:]

                    _amount = int(float_round(line['kwota'], precision_digits=0))  # rounded to integer
                    etree.SubElement(sale_row, etree.QName(f'P_{prefix}c')).text = str(_amount)
                    group_vals['amount'] = _amount

                    if group != 'group3':
                        _tt = '1' if any(flag in ['TT_WNT', 'TT_D'] for flag in _flags) else '2'
                        etree.SubElement(sale_row, etree.QName(f'P_{prefix}d')).text = _tt

                        # Set tt to 'X' or '-' to show in view/report
                        group_vals['tt'] = 'X' if _tt == '2' else '-'

                    group_vals_list[group].append(group_vals)

        return etree.tostring(deklaracja, encoding='UTF-8', xml_declaration=True, pretty_print=True), group_vals_list

    @staticmethod
    def _get_query_vat_ue():
        # noinspection SqlResolve
        return """SELECT
              p.vat                                    AS NrKontrahenta,
              p.name                                   AS NazwaKontrahenta,
              p.id                                     AS PartnerId,
              jat.jpk_markup                           AS JPKMarkup,
              jat.jpk_v7_group as v7group,
              CASE
                  WHEN right(jat.jpk_v7_group, 3) = '_21' THEN 'group1'
                  WHEN right(jat.jpk_v7_group, 3) = '_23' THEN 'group2'
                  WHEN right(jat.jpk_v7_group, 3) = '_12' THEN 'group3'
              END                                      AS JPKGroup,
              STRING_AGG(distinct (jpk_gtu.name), ',') AS GTU,
              CONCAT_WS(',', CASE WHEN am.x_pl_vat_tt_wnt THEN 'TT_WNT' END,
                        CASE WHEN am.x_pl_vat_tt_d THEN 'TT_D' END
                   )                                   AS Flags,
              SUM(CASE
                      WHEN aml.tax_line_id IS NOT NULL and jat.jpk_section = 'ZakupWiersz'
                          then aml.balance
                      WHEN aml.tax_line_id IS NOT NULL and jat.jpk_section = 'SprzedazWiersz'
                          then - aml.balance
                      WHEN jat.jpk_section = 'SprzedazWiersz' and am.move_type in ('out_invoice', 'out_refund', 'entry')
                          then - aml.balance
                      ELSE (aml.balance)
                  END)                                 AS kwota
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
                AND aat.id in %(account_tags)s
                AND p.vat NOT LIKE 'PL%%'
       GROUP BY NrKontrahenta, NazwaKontrahenta, PartnerId, Flags, JPKMarkup, v7group, JPKGroup
       ORDER BY JPKMarkup, JPKGroup"""
