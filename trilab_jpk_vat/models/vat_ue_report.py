import re

from lxml import etree

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
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

    def _prepare_common_xml_fields(self, tns, tns_etd, options):
        company = self.env.company
        if not (company.pl_tax_office_id and company.pl_tax_office_id.code):
            raise UserError(_('PL Tax Office is not set for company %s', company.name))

        deklaracja = etree.Element(etree.QName('Deklaracja'), nsmap={None: tns, 'etd': tns_etd})
        header = etree.SubElement(deklaracja, etree.QName('Naglowek'))

        etree.SubElement(
            header,
            etree.QName('KodFormularza'),
            attrib={'kodSystemowy': options['systemCode'], 'wersjaSchemy': options['schemaVersion']},
        ).text = options['formCode']
        etree.SubElement(header, etree.QName('WariantFormularza')).text = options['formVariant']

        report_date = fields.Date.to_date(options['date']['date_from'])
        etree.SubElement(header, etree.QName('Rok')).text = str(report_date.year)
        etree.SubElement(header, etree.QName('Miesiac')).text = str(report_date.month)

        etree.SubElement(header, etree.QName('CelZlozenia')).text = '1'
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

        return deklaracja, pozycje_szczegolowe

    def get_xml_extended_vat_ue(self, options):
        # noinspection HttpUrlsUsage
        tns = 'http://crd.gov.pl/wzor/2021/01/12/10293/'
        # noinspection HttpUrlsUsage
        tns_etd = 'http://crd.gov.pl/xml/schematy/dziedzinowe/mf/2020/03/11/eD/DefinicjeTypy/'

        deklaracja, pozycje_szczegolowe = self._prepare_common_xml_fields(
            tns,
            tns_etd,
            options={
                'date': options['date'],
                'formCode': 'VAT-UE',
                'formVariant': '5',
                'systemCode': 'VAT-UE (5)',
                'schemaVersion': '2-0E',
            },
        )

        group_vals_list = {'group1': [], 'group2': [], 'group3': [], 'group4': []}

        ctx = self._set_context(options)

        # deactivating the prefetching saves ~35% on get_lines running time
        ctx.update({'no_format': True, 'print_mode': False, 'prefetch_fields': False, 'dict_output': True})
        # noinspection PyProtectedMember
        groups = self.with_context(ctx)._get_lines_vat_ue(options)

        if groups:
            for group in ['group1', 'group2', 'group3', 'group4']:
                for line in groups.get(group, []):
                    sale_row = etree.SubElement(pozycje_szczegolowe, etree.QName(self.GROUP_MAPPING[group]['name']))

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
                        # check whether the item is related to triangular transactions:
                        # 1 - item DOES NOT apply to trilateral transactions
                        # 2 - item applies to trilateral transactions
                        _tt = '2' if any(flag in ('TT_WNT', 'TT_D') for flag in _flags) else '1'
                        etree.SubElement(sale_row, etree.QName(f'P_{prefix}d')).text = _tt

                        # Set tt to 'X' or '-' to show in view/report
                        group_vals['tt'] = 'X' if _tt == '2' else '-'

                    group_vals_list[group].append(group_vals)

        return etree.tostring(deklaracja, encoding='UTF-8', xml_declaration=True, pretty_print=True), group_vals_list

    def get_xml_extended_vat_uek(self, options):
        # noinspection HttpUrlsUsage
        tns = 'http://crd.gov.pl/wzor/2021/01/26/10316/'
        # noinspection HttpUrlsUsage
        tns_etd = 'http://crd.gov.pl/xml/schematy/dziedzinowe/mf/2020/03/11/eD/DefinicjeTypy/'

        deklaracja, pozycje_szczegolowe = self._prepare_common_xml_fields(
            tns,
            tns_etd,
            options={
                'date': options['date'],
                'formCode': 'VAT-UEK',
                'formVariant': '5',
                'systemCode': 'VATUEK (5)',
                'schemaVersion': '2-1E',
            },
        )

        group_vals_list = {'group1': [], 'group2': [], 'group3': [], 'group4': []}

        ctx = self._set_context(options)

        # deactivating the prefetching saves ~35% on get_lines running time
        ctx.update({'no_format': True, 'print_mode': False, 'prefetch_fields': False, 'dict_output': True})
        # noinspection PyProtectedMember
        groups = self.with_context(ctx)._get_lines_vat_ue(options)

        original_vat_ue_id = self.env['jpk.vat.ue'].browse(options.get('original_vat_ue_id')).exists()

        if not original_vat_ue_id:
            raise ValidationError(_('Original VAT UE report not found!'))

        if not groups:
            return (
                etree.tostring(deklaracja, encoding='UTF-8', xml_declaration=True, pretty_print=True),
                group_vals_list,
            )

        for group in ['group1', 'group2', 'group3', 'group4']:
            group_lines = {}

            corr_lines = {
                self.env['res.partner'].browse(_l['partnerid']).x_get_eu_vat(): _l for _l in groups.get(group, [])
            }
            orig_lines = {f'{_l.country_code}{_l.nip}': _l for _l in getattr(original_vat_ue_id, f'{group}_line_ids')}

            for partner_id in corr_lines.keys():
                group_lines[partner_id] = (corr_lines[partner_id], orig_lines.get(partner_id))

            for partner_id in orig_lines.keys():
                if partner_id not in group_lines:
                    group_lines[partner_id] = (None, orig_lines[partner_id])

            for vat, (corr_line, orig_line) in group_lines.items():
                group_vals = {}

                if corr_line:  # prepare values for new UE group lines
                    _flags = set(corr_line['flags'].split(',')) if corr_line['flags'] else set()
                    _taxes = set()

                    group_vals['vat'] = vat and vat[2:]
                    group_vals['country_code'] = vat and vat[:2]
                    _amount = int(float_round(corr_line['kwota'], precision_digits=0))  # rounded to integer
                    group_vals['amount'] = _amount

                    if group != 'group3':
                        # check whether the item is related to triangular transactions:
                        # 1 - item DOES NOT apply to trilateral transactions
                        # 2 - item applies to trilateral transactions
                        _tt = '2' if any(flag in ('TT_WNT', 'TT_D') for flag in _flags) else '1'
                        # Set tt to 'X' or '-' to show in view/report
                        group_vals['tt'] = 'X' if _tt == '2' else '-'

                    group_vals_list[group].append(group_vals)

                sale_row = etree.SubElement(pozycje_szczegolowe, etree.QName(self.GROUP_MAPPING[group]['name']))
                prefix = self.GROUP_MAPPING[group]['prefix']

                if orig_line is None:
                    orig_line = self.env['jpk.vat.ue.group']

                xml_values = {}

                if orig_line:
                    xml_values.update(
                        {
                            f'P_{prefix}Ba': orig_line.country_code,
                            f'P_{prefix}Bb': orig_line.nip,
                            f'P_{prefix}Bc': str(int(orig_line.amount)),
                            f'P_{prefix}Bd': ('2' if orig_line.tt == 'X' else '1') if group != 'group3' else None,
                        }
                    )
                if corr_line:
                    xml_values.update(
                        {
                            f'P_{prefix}Ja': group_vals.get('country_code', 'BRAK'),
                            f'P_{prefix}Jb': group_vals.get('vat', 'BRAK'),
                            f'P_{prefix}Jc': str(group_vals.get('amount', 0)),
                            f'P_{prefix}Jd': ('2' if group_vals.get('tt') == 'X' else '1')
                            if group != 'group3'
                            else None,
                        }
                    )

                for tag_name, tag_value in xml_values.items():
                    if tag_value is not None:
                        etree.SubElement(sale_row, etree.QName(tag_name)).text = tag_value

        return etree.tostring(deklaracja, encoding='UTF-8', xml_declaration=True, pretty_print=True), group_vals_list

    @staticmethod
    def _get_query_vat_ue():
        # noinspection SqlResolve
        return """SELECT
              p.vat                                    AS NrKontrahenta,
              (array_agg(distinct coalesce(p.name, p.display_name)))[1] AS NazwaKontrahenta,
              (array_agg(p.id))[1]                                      AS PartnerId,
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
                AND aml.display_type IS NULL
       GROUP BY NrKontrahenta, Flags, JPKMarkup, v7group, JPKGroup
       ORDER BY JPKMarkup, JPKGroup"""
