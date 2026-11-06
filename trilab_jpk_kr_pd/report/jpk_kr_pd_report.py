import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from functools import cached_property
from typing import Optional

from lxml import etree
from lxml.builder import ElementMaker

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import SQL, float_repr
from odoo.tools.translate import LazyGettext, _lt

from odoo.addons.trilab_jpk_base.models.export_helper import XlsxHelper


@dataclass(frozen=True)
class KrPdColumn:
    name: str
    label: str | LazyGettext
    is_optional: bool = False
    is_number: bool = False
    is_date: bool = False

    @cached_property
    def name_lower(self) -> str:
        return self.name.lower()


@dataclass(frozen=True)
class KrPdSectionErrorMap:
    object_name: str | LazyGettext
    object_identifier: str


@dataclass(eq=False)
class KrPdSection:
    name: str
    title: str
    columns: tuple[KrPdColumn, ...]
    error_map: Optional['KrPdSectionErrorMap'] = None
    counters_map: tuple[tuple[str, str], ...] | None = None
    sub_section: Optional['KrPdSection'] = None
    debit_skip: tuple[str, ...] | None = None
    credit_skip: tuple[str, ...] | None = None

    @cached_property
    def name_lower(self) -> str:
        return self.name.lower()

    @cached_property
    def column_names(self) -> tuple[str, ...]:
        return tuple(column.name for column in self.columns)

    @cached_property
    def column_names_lower(self) -> tuple[str, ...]:
        return tuple(column.name_lower for column in self.columns)


class KrPdData:
    kontrahent = KrPdSection(
        name='Kontrahent',
        title='Kontrahent',
        columns=(
            KrPdColumn('T_1', _lt('Partner Code')),
            KrPdColumn('T_2', _lt('Country Code'), is_optional=True),
            KrPdColumn('T_3', _lt('VAT Number'), is_optional=True),
        ),
        error_map=KrPdSectionErrorMap(object_name=_lt('Partner'), object_identifier='t_1'),
    )

    zois = KrPdSection(
        name='ZOiS',
        title='Zestawienie obrotów i sald',
        columns=(
            KrPdColumn('S_1', _lt('Account')),
            KrPdColumn('S_2', _lt('Account Name')),
            KrPdColumn('S_3', _lt('Parent Account')),
            KrPdColumn('S_4', _lt('Opening Debit Balance'), is_number=True),
            KrPdColumn('S_5', _lt('Opening Credit Balance'), is_number=True),
            KrPdColumn('S_6', _lt('Debit Turnover'), is_number=True),
            KrPdColumn('S_7', _lt('Credit Turnover'), is_number=True),
            KrPdColumn('S_8', _lt('Cumulative Debit Turnover'), is_number=True),
            KrPdColumn('S_9', _lt('Cumulative Credit Turnover'), is_number=True),
            KrPdColumn('S_10', _lt('Debit Balance'), is_number=True),
            KrPdColumn('S_11', _lt('Credit Balance'), is_number=True),
            KrPdColumn('S_12_1', _lt('Account Tag')),
            KrPdColumn('S_12_2', _lt('Account Tag 2'), is_optional=True),
            KrPdColumn('S_12_3', _lt('Tax Tag'), is_optional=True),
        ),
        error_map=KrPdSectionErrorMap(object_name=_lt('Account'), object_identifier='s_1'),
    )

    dziennik = KrPdSection(
        name='Dziennik',
        title='Dziennik',
        columns=(
            KrPdColumn('D_1', _lt('Entry Number')),
            KrPdColumn('D_2', _lt('Journal Description')),
            KrPdColumn('D_3', _lt('Partner Code'), is_optional=True),
            KrPdColumn('D_4', _lt('Document Number')),
            KrPdColumn('D_5', _lt('Document Type')),
            KrPdColumn('D_6', _lt('Transaction Date'), is_date=True),
            KrPdColumn('D_7', _lt('Document Date'), is_date=True),
            KrPdColumn('D_8', _lt('Posting Date'), is_date=True),
            KrPdColumn('D_9', _lt('Entered By')),
            KrPdColumn('D_10', _lt('Transaction Description')),
            KrPdColumn('D_11', _lt('Transaction Amount'), is_number=True),
        ),
        error_map=KrPdSectionErrorMap(object_name=_lt('Journal Entry'), object_identifier='move_name'),
        counters_map=(('d_11', 'C_2'),),
        sub_section=KrPdSection(
            name='KontoZapis',
            title='Zapisy na kontach księgi głównej i ksiąg pomocniczych',
            columns=(
                KrPdColumn('Z_1', _lt('Entry Number')),
                KrPdColumn('Z_2', _lt('Entry Line Description')),
                KrPdColumn('Z_3', _lt('Account')),
                KrPdColumn('Z_4', _lt('Debit Amount'), is_number=True),
                KrPdColumn('Z_5', _lt('Debit Amount in Foreign Currency'), is_optional=True, is_number=True),
                KrPdColumn('Z_6', _lt('Debit Currency'), is_optional=True),
                KrPdColumn('Z_7', _lt('Credit Amount'), is_number=True),
                KrPdColumn('Z_8', _lt('Credit Amount in Foreign Currency'), is_optional=True, is_number=True),
                KrPdColumn('Z_9', _lt('Credit Currency'), is_optional=True),
            ),
            error_map=KrPdSectionErrorMap(object_name=_lt('Line of Journal Entry'), object_identifier='move_name'),
            counters_map=(('z_4', 'C_4'), ('z_7', 'C_5')),
            debit_skip=('Z_7', 'Z_8', 'Z_9'),
            credit_skip=('Z_4', 'Z_5', 'Z_6'),
        ),
    )

    rpd = KrPdSection(
        name='RPD',
        title='RPD',
        columns=(
            KrPdColumn('K_1', _lt('Permanently Exempt Revenue'), is_number=True),
            KrPdColumn('K_2', _lt('Revenue Deferred to Future Years'), is_number=True),
            KrPdColumn('K_3', _lt('Revenue Recognized from Previous Years'), is_number=True),
            KrPdColumn('K_4', _lt('Permanently Non-Deductible Costs'), is_number=True),
            KrPdColumn('K_5', _lt('Costs Deferred to Future Years'), is_number=True),
            KrPdColumn('K_6', _lt('Costs Recognized from Previous Years'), is_number=True),
            KrPdColumn('K_7', _lt('Additional Off-Book Revenue'), is_number=True),
            KrPdColumn('K_8', _lt('Off-Book Recognized Costs'), is_number=True),
        ),
    )

    SECTIONS: list[KrPdSection] = [kontrahent, zois, dziennik, rpd]


# noinspection HttpUrlsUsage
NS_TNS = 'http://jpk.mf.gov.pl/wzor/2024/09/04/09041/'

# noinspection HttpUrlsUsage
NS_ETD = 'http://crd.gov.pl/xml/schematy/dziedzinowe/mf/2022/01/05/eD/DefinicjeTypy/'

NSMAP = {
    'tns': NS_TNS,
    'etd': NS_ETD,
}


def _serialize_bool(element, value):
    element.text = '1' if value else '2'


def _serialize_float(element, value):
    element.text = float_repr(value, 2)


def _serialize_integer(element, value):
    element.text = str(value)


def _serialize_date(element, value):
    element.text = value.isoformat()


def _serialize_datetime(element, value):
    element.text = value.isoformat()


NS_TYPES = {
    bool: _serialize_bool,
    float: _serialize_float,
    int: _serialize_integer,
    date: _serialize_date,
    datetime: _serialize_datetime,
}

Etns = ElementMaker(typemap=NS_TYPES, namespace=NS_TNS, nsmap=NSMAP)
Eetd = ElementMaker(typemap=NS_TYPES, namespace=NS_ETD, nsmap=NSMAP)


class JpkKrPdReport(models.AbstractModel):
    _name = 'report.trilab_jpk_kr_pd.jpk_kr_pd_report'
    _inherit = 'jpk.trilab.export_helper'
    _description = 'JPK KR PD Report'

    xlsx_styles = XlsxHelper.xlsx_styles | {'monetary': {'font_size': 12, 'num_format': '# ##0.00'}}

    def _get_zois(self, options):
        # noinspection SqlResolve
        query = """
                WITH amls AS (SELECT amls_union.account_id,
                                     amls_union.pd_code,
                                     amls_union.is_wynikowe,
                                     SUM(amls_union.bo_debit)  AS bo_debit,
                                     SUM(amls_union.bo_credit) AS bo_credit,
                                     SUM(amls_union.o_debit)   AS o_debit,
                                     SUM(amls_union.o_credit)  AS o_credit
                              FROM (SELECT
                                        aml.account_id,
                                        pd.pd_code,
                                        aa.account_type LIKE 'expense%%' OR aa.account_type LIKE 'income%%'
                                                                                                         AS is_wynikowe,
                                        SUM(CASE WHEN aml.date < %(date_from)s THEN aml.debit ELSE 0 END)  AS bo_debit,
                                        SUM(CASE WHEN aml.date < %(date_from)s THEN aml.credit ELSE 0 END) AS bo_credit,
                                        SUM(CASE
                                              WHEN aml.date BETWEEN %(date_from)s AND %(date_to)s THEN aml.debit
                                              ELSE 0 END)                                                 AS o_debit,
                                        SUM(CASE
                                              WHEN aml.date BETWEEN %(date_from)s AND %(date_to)s THEN aml.credit
                                              ELSE 0 END)                                                 AS o_credit
                                    FROM account_move_line AS aml
                                             JOIN account_move AS am
                                                  ON am.id = aml.move_id
                                             JOIN account_account AS aa
                                                  ON aa.id = aml.account_id
                                             LEFT JOIN LATERAL (
                                        SELECT aaa.code AS pd_code
                                        FROM jsonb_each(aml.analytic_distribution) AS ad(key, value)
                                                 JOIN LATERAL unnest(string_to_array(ad.key, ',')) AS aaa_id(id) ON TRUE
                                                 JOIN account_analytic_account AS aaa ON aaa.id = aaa_id.id::int
                                                 JOIN account_analytic_plan AS aap ON aap.id = aaa.plan_id
                                        WHERE aap.x_pl_jpk_kr_pd = true
                                        LIMIT 1
                                        ) pd ON TRUE
                                    WHERE am.state = %(move_state)s
                                      AND am.company_id = %(company_id)s
                                      AND aml.date <= %(date_to)s
                                      AND aml.display_type NOT IN ('line_section', 'line_note')
                                    GROUP BY aml.account_id, aa.account_type, pd.pd_code

                                    UNION ALL

                                    SELECT aa_cye.id       AS account_id,
                                           pd.pd_code,
                                           FALSE           AS is_wynikowe,
                                           SUM(aml.debit)  AS bo_debit,
                                           SUM(aml.credit) AS bo_credit,
                                           0               AS o_debit,
                                           0               AS o_credit
                                    FROM account_move_line AS aml
                                             JOIN account_move AS am
                                                  ON am.id = aml.move_id
                                             JOIN account_account AS aa_src
                                                  ON aa_src.id = aml.account_id
                                             JOIN account_account AS aa_cye
                                                  ON aa_cye.account_type = 'equity_unaffected'
                                                      AND EXISTS (SELECT 1
                                                                  FROM account_account_res_company_rel rel
                                                                  WHERE rel.account_account_id = aa_cye.id
                                                                    AND rel.res_company_id = %(company_id)s)
                                             LEFT JOIN LATERAL (
                                        SELECT aaa.code AS pd_code
                                        FROM jsonb_each(aml.analytic_distribution) AS ad(key, value)
                                                 JOIN LATERAL unnest(string_to_array(ad.key, ',')) AS aaa_id(id) ON TRUE
                                                 JOIN account_analytic_account AS aaa ON aaa.id = aaa_id.id::int
                                                 JOIN account_analytic_plan AS aap ON aap.id = aaa.plan_id
                                        WHERE aap.x_pl_jpk_kr_pd = true
                                        LIMIT 1
                                        ) pd ON TRUE
                                    WHERE (aa_src.account_type LIKE 'expense%%' OR aa_src.account_type LIKE 'income%%')
                                      AND am.state = %(move_state)s
                                      AND am.company_id = %(company_id)s
                                      AND aml.date < date_trunc('year', %(date_from)s::date)
                                      AND aml.display_type NOT IN ('line_section', 'line_note')
                                    GROUP BY aa_cye.id, pd.pd_code) amls_union
                              GROUP BY amls_union.account_id, amls_union.pd_code, amls_union.is_wynikowe)

                SELECT aa.code_store ->> %(company_id)s::text || COALESCE('.' || amls.pd_code, '')          AS S_1,
                       COALESCE(aa.name ->> %(lang)s, aa.name ->> 'en_US')                                  AS S_2,
                       COALESCE(ag.name, aa.code_store ->> %(company_id)s::text)                            AS S_3,
                       ROUND(CASE WHEN amls.is_wynikowe THEN 0 ELSE GREATEST(amls.bo_debit - amls.bo_credit, 0) END,
                             2)                                                                             AS S_4,
                       ROUND(CASE WHEN amls.is_wynikowe THEN 0 ELSE GREATEST(amls.bo_credit - amls.bo_debit, 0) END,
                             2)                                                                             AS S_5,
                       ROUND(amls.o_debit, 2)                                                               AS S_6,
                       ROUND(amls.o_credit, 2)                                                              AS S_7,
                       ROUND((CASE
                                  WHEN amls.is_wynikowe THEN 0
                                  ELSE GREATEST(amls.bo_debit - amls.bo_credit, 0) END) + amls.o_debit, 2)  AS S_8,
                       ROUND((CASE
                                  WHEN amls.is_wynikowe THEN 0
                                  ELSE GREATEST(amls.bo_credit - amls.bo_debit, 0) END) + amls.o_credit, 2) AS S_9,
                       GREATEST(ROUND(CASE
                                          WHEN amls.is_wynikowe THEN amls.o_debit - amls.o_credit
                                          ELSE (amls.bo_debit + amls.o_debit) - (amls.bo_credit + amls.o_credit)
                                          END, 2), 0)                                                       AS S_10,
                       GREATEST(ROUND(CASE
                                          WHEN amls.is_wynikowe THEN amls.o_credit - amls.o_debit
                                          ELSE (amls.bo_credit + amls.o_credit) - (amls.bo_debit + amls.o_debit)
                                          END, 2), 0)                                                       AS S_11,

                       (SELECT REPLACE(aat.name ->> 'en_US', 'S_12_1__', '')
                        FROM account_account_account_tag AS aaat
                                 JOIN account_account_tag AS aat
                                      ON aat.id = aaat.account_account_tag_id
                        WHERE aaat.account_account_id = aa.id
                          AND starts_with(aat.name ->> 'en_US', 'S_12_1__')
                        LIMIT 1)                                                                            AS S_12_1,
                       (SELECT REPLACE(aat.name ->> 'en_US', 'S_12_2__', '')
                        FROM account_account_account_tag AS aaat
                                 JOIN account_account_tag AS aat
                                      ON aat.id = aaat.account_account_tag_id
                        WHERE aaat.account_account_id = aa.id
                          AND starts_with(aat.name ->> 'en_US', 'S_12_2__')
                        LIMIT 1)                                                                            AS S_12_2,
                       amls.pd_code                                                                         AS S_12_3
                FROM account_account AS aa
                         JOIN amls
                              ON amls.account_id = aa.id
                         LEFT JOIN LATERAL (
                            SELECT concat_ws(
                                           ' ',
                                           CASE
                                               WHEN ag.code_prefix_end = ag.code_prefix_start THEN ag.code_prefix_start
                                               ELSE ag.code_prefix_start || '-' || ag.code_prefix_end
                                               END,
                                           COALESCE(ag.name ->> %(lang)s, ag.name ->> 'en_US')
                                   ) AS name
                            FROM account_group AS ag
                            WHERE ag.code_prefix_start <=
                                  LEFT(aa.code_store ->> %(company_id)s::text, char_length(ag.code_prefix_start))
                              AND ag.code_prefix_end >=
                                  LEFT(aa.code_store ->> %(company_id)s::text, char_length(ag.code_prefix_end))
                              AND ag.company_id = %(company_id)s
                            ORDER BY char_length(ag.code_prefix_start) DESC, ag.id
                            LIMIT 1) AS ag ON TRUE
                ORDER BY S_1
                """

        self.env.cr.execute(
            query,
            {
                'date_from': fields.Datetime.from_string(options.get('date_from')),
                'date_to': fields.Datetime.from_string(options.get('date_to')),
                'move_state': 'posted',
                'company_id': options.get('company_id'),
                'lang': self.env.ref('base.lang_pl').code,
            },
        )

        return self.env.cr.dictfetchall()

    def _get_kontrahent(self, options):
        result = []

        for partner_id in self.env['res.partner'].browse(
            [
                partner[0]
                for partner in self.env.execute_query(
                    SQL(
                        """
                        SELECT DISTINCT am.partner_id
                        FROM account_move AS am
                        WHERE am.date BETWEEN %(date_from)s AND %(date_to)s
                          AND am.state = 'posted'
                          AND am.company_id = %(company_id)s
                          AND am.partner_id IS NOT NULL
                        ORDER BY am.partner_id
                        """,
                        date_from=fields.Datetime.from_string(options.get('date_from')),
                        date_to=fields.Datetime.from_string(options.get('date_to')),
                        company_id=options.get('company_id'),
                    ),
                )
            ],
        ):
            vat, country_code = partner_id.x_get_jpk_vat_and_country()
            result.append({'t_1': partner_id.id, 't_2': country_code, 't_3': vat})

        return result

    def _get_dziennik(self, options):
        # noinspection SqlResolve
        self.env.cr.execute(
            SQL(
                """
                SELECT am.x_journal_entry_number                               AS D_1,
                       COALESCE(aj.name ->> 'pl_PL', aj.name ->> 'en_US')      AS D_2,
                       am.partner_id                                           AS D_3,
                       CASE
                           WHEN am.move_type IN ('in_invoice', 'in_refund') THEN COALESCE(am.ref, am.name)
                           ELSE am.name
                           END                                                 AS D_4,
                       CASE
                           WHEN aj.type = 'purchase' THEN 'Zakup'
                           WHEN aj.type = 'sale' THEN 'Sprzedaż'
                           WHEN aj.type = 'bank' THEN 'Bank'
                           WHEN aj.type = 'cash' THEN 'Kasa'
                           ELSE 'Różne'
                           END                                                 AS D_5,
                       %(transaction_date)s                                    AS D_6,
                       COALESCE(am.invoice_date, CAST(am.create_date AS date)) AS D_7,
                       am.date                                                 AS D_8,
                       ru.login                                                AS D_9,
                       COALESCE(MAX(aml_to_desc2.name), am.ref, am.name)       AS D_10,
                       am.amount_total                                         AS D_11,
                       am.name                                                 AS move_name,
                       json_agg(
                               json_build_object(
                                       'z_1', (SELECT COUNT(*)
                                               FROM account_move_line AS aml2
                                               WHERE aml2.move_id = aml.move_id
                                                 AND aml2.display_type NOT IN ('line_section', 'line_note')
                                                 AND aml2.id <= aml.id),
                                       'z_2', COALESCE(aml.name, am.name),
                                       'z_3',
                                       (aa.code_store ->> %(company_id)s::text || COALESCE('.' || pd.pd_code, '')),
                                       'z_4', CASE
                                                  WHEN aml.balance > 0
                                                      THEN aml.debit
                                                  ELSE 0
                                           END,
                                       'z_5', CASE
                                                  WHEN aml.amount_currency > 0
                                                      THEN aml.amount_currency
                                                  ELSE 0
                                           END,
                                       'z_6', CASE
                                                  WHEN aml.amount_currency > 0
                                                      THEN rc.name
                                           END,
                                       'z_7', CASE
                                                  WHEN aml.balance < 0
                                                      THEN aml.credit
                                                  ELSE 0
                                           END,
                                       'z_8', CASE
                                                  WHEN aml.amount_currency < 0
                                                      THEN -aml.amount_currency
                                                  ELSE 0
                                           END,
                                       'z_9', CASE
                                                  WHEN aml.amount_currency < 0
                                                      THEN rc.name
                                           END,
                                       'move_name', am.name
                               ) ORDER BY aml.id)                              AS lines
                FROM account_move AS am
                         LEFT JOIN account_journal AS aj
                                   ON aj.id = am.journal_id
                         LEFT JOIN res_users AS ru
                                   ON ru.id = am.write_uid
                         LEFT JOIN (SELECT MIN(id) AS id,
                                           move_id
                                    FROM account_move_line
                                    WHERE display_type = 'product'
                                    GROUP BY move_id) AS aml_to_desc1 ON aml_to_desc1.move_id = am.id
                         LEFT JOIN account_move_line AS aml_to_desc2 ON aml_to_desc2.id = aml_to_desc1.id
                         LEFT JOIN account_move_line AS aml
                                   ON aml.move_id = am.id
                                       AND aml.display_type NOT IN ('line_section', 'line_note')
                         LEFT JOIN account_account AS aa
                                   ON aa.id = aml.account_id
                         LEFT JOIN res_currency AS rc
                                   ON rc.id = aml.currency_id
                         LEFT JOIN LATERAL (
                    SELECT aaa.code AS pd_code
                    FROM jsonb_each(aml.analytic_distribution) ad(key, value)
                             JOIN LATERAL unnest(string_to_array(ad.key, ',')) AS aaa_id(id)
                                  ON TRUE
                             JOIN account_analytic_account aaa ON aaa.id = aaa_id.id::int
                             JOIN account_analytic_plan aap
                                  ON aap.id = aaa.plan_id
                    WHERE aap.x_pl_jpk_kr_pd = true
                    LIMIT 1) AS pd
                                   ON TRUE
                WHERE am.date BETWEEN %(date_from)s
                    AND %(date_to)s
                  AND am.state = 'posted'
                  AND am.company_id = %(company_id)s
                GROUP BY am.id, aj.id, ru.id
                """,
                transaction_date=SQL(
                    """
                    CASE
                        WHEN am.move_type = 'entry' THEN CAST(am.create_date AS date)
                        ELSE COALESCE(am.x_invoice_sale_date, CAST(am.create_date AS date))
                    END
                    """
                    if 'x_invoice_sale_date' in self.env['account.move']._fields
                    else 'CAST(am.create_date AS date)',
                ),
                date_from=fields.Datetime.from_string(options.get('date_from')),
                date_to=fields.Datetime.from_string(options.get('date_to')),
                company_id=options.get('company_id'),
            ),
        )

        return self.env.cr.dictfetchall()

    def _get_rpd(self, options):
        # noinspection SqlResolve
        query = """
                SELECT ROUND(COALESCE(SUM(aml.credit - aml.debit) FILTER (WHERE pd.pd_code LIKE 'PD1%%'), 0), 2) AS K_1,
                       ROUND(COALESCE(SUM(aml.credit - aml.debit) FILTER (WHERE pd.pd_code LIKE 'PD2%%'), 0), 2) AS K_2,
                       ROUND(COALESCE(SUM(aml.credit - aml.debit) FILTER (WHERE pd.pd_code LIKE 'PD3%%'), 0), 2) AS K_3,
                       ROUND(COALESCE(SUM(aml.debit - aml.credit) FILTER (WHERE pd.pd_code LIKE 'PD4%%'), 0), 2) AS K_4,
                       ROUND(COALESCE(SUM(aml.debit - aml.credit) FILTER (WHERE pd.pd_code LIKE 'PD5%%'), 0), 2) AS K_5,
                       ROUND(COALESCE(SUM(aml.debit - aml.credit) FILTER (WHERE pd.pd_code LIKE 'PD6%%'), 0), 2) AS K_6,
                       ROUND(COALESCE(
                                             SUM(aml.credit - aml.debit)
                                             FILTER (
                                                 WHERE (pd.pd_code LIKE 'PD7%%' AND pd.pd_code NOT IN ('PD7', 'PD7_PB'))
                                                       OR pd.pd_code IN ('PD8_1', 'PD8_PB_1')
                                             ), 0
                                     ), 2)                                                                       AS K_7,
                       ROUND(COALESCE(
                                             SUM(aml.debit - aml.credit)
                                             FILTER (
                                                 WHERE (pd.pd_code LIKE 'PD8%%'
                                                        AND pd.pd_code NOT IN ('PD8_1', 'PD8_PB_1'))
                                                       OR pd.pd_code IN ('PD7', 'PD7_PB')
                                                 ), 0
                             ), 2)                                                                               AS K_8
                FROM account_move_line AS aml
                         JOIN account_move AS am
                              ON am.id = aml.move_id
                         LEFT JOIN LATERAL (
                    SELECT aaa.code AS pd_code
                    FROM jsonb_each(aml.analytic_distribution) ad(key, value)
                             JOIN LATERAL unnest(string_to_array(ad.key, ',')) AS aaa_id(id)
                                  ON TRUE
                             JOIN account_analytic_account AS aaa
                                  ON aaa.id = aaa_id.id::int
                             JOIN account_analytic_plan AS aap
                                  ON aap.id = aaa.plan_id
                    WHERE aap.x_pl_jpk_kr_pd = true
                    LIMIT 1) AS pd
                                   ON TRUE
                WHERE am.date BETWEEN %s
                    AND %s
                  AND am.state = 'posted'
                  AND am.company_id = %s
                """

        self.env.cr.execute(
            query,
            (
                fields.Datetime.from_string(options.get('date_from')),
                fields.Datetime.from_string(options.get('date_to')),
                options.get('company_id'),
            ),
        )

        return self.env.cr.dictfetchall()

    @api.model
    def _raise_error(self, section, line, column):
        raise UserError(
            _(
                '%s %s is missing required information for field %s.',
                section.error_map.object_name,
                line[section.error_map.object_identifier],
                f'{column.name} {column.label}',
            ),
        )

    @api.model
    def _get_section_lines(self, options, section, data):
        lines = []

        for line in data:
            line_values = {'values': [line.get(name) for name in section.column_names_lower]}

            for idx, column in enumerate(section.columns):
                value = line_values['values'][idx]

                if value is not None:
                    if column.is_number:
                        line_values['values'][idx] = float_repr(value, 2) if value is not None else value

                elif not column.is_optional:
                    self._raise_error(section=section, line=line, column=column)

            if (sub_section := section.sub_section) and (sub_lines := line.get('lines')):
                line_values |= {'lines': self._get_section_lines(options, sub_section, sub_lines)}

            lines.append(line_values)

        return lines

    @api.model
    def _get_report_data(self, doc_ids, options):
        data = {'sections': {}}

        for section in KrPdData.SECTIONS:
            data['sections'] |= {
                section: {
                    'lines': self._get_section_lines(
                        options, section, data=getattr(self, f'_get_{section.name_lower}')(options),
                    ),
                },
            }

        return data

    def _get_report_values(self, docids, data):
        return {
            'company_name': self.env['res.company'].browse(data['company_id']).display_name,
            'date_to': data['date_to'],
            'date_from': data['date_from'],
            'doc': self._get_report_data(doc_ids=docids, options=data),
        }

    def process_section(
        self, options, section: KrPdSection, element_name=None, lines=None, counter=None, currency_id=None,
    ):
        elements = []

        for line in lines or getattr(self, f'_get_{section.name_lower}')(options):
            sub_elements = []

            if counter is not None and section.counters_map:
                counter[f'{section.name_lower}_lines'] += 1

                for counter_field, section_field in section.counters_map:
                    counter[section_field] += line.get(counter_field, 0.0)

            for column in section.columns:
                if currency_id and (credit_skip := section.credit_skip) and (debit_skip := section.debit_skip):
                    # Skip KontoZapis credit fields when Z_4 (debit amount) == 0, otherwise skip debit fields.
                    if (
                        ((is_z_4_zero := currency_id.is_zero(line.get('z_4', 0.0)))
                        and column.name in credit_skip)
                        or (not is_z_4_zero
                        and column.name in debit_skip)
                    ):
                        continue

                if (value := line.get(column.name_lower)) is not None:
                    sub_elements.append(Etns(column.name, value))

                elif not column.is_optional:
                    self._raise_error(section=section, line=line, column=column)

            if section.sub_section and (lines := line.get('lines')):
                sub_elements.extend(
                    self.process_section(
                        options=options,
                        section=section.sub_section,
                        lines=lines,
                        counter=counter,
                        currency_id=currency_id,
                    ),
                )

            elements.append(Etns(element_name or section.name, *sub_elements))

        return elements

    def get_xml(self, options):
        company_id = self.env['res.company'].browse(options['company_id'])
        company_currency_id = company_id.currency_id

        if company_id.company_registry:
            podmiot1_regon = [Eetd.REGON(company_id.company_registry)]

        else:
            podmiot1_regon = []

        if company_id.country_id == self.env.ref('base.pl'):
            podmiot1_addr = Etns.AdresPol(
                Eetd.KodKraju(company_id.country_id.code),
                Eetd.Wojewodztwo(company_id.state_id.name),
                Eetd.Powiat(company_id.pl_county),
                Eetd.Gmina(company_id.pl_community),
                Eetd.Ulica(company_id.x_street_short),
                Eetd.NrDomu(company_id.x_street_short_number or 'brak'),
                Eetd.Miejscowosc(company_id.city),
                Eetd.KodPocztowy(company_id.zip),
            )

        else:
            podmiot1_addr = Etns.AdresZagr(
                Eetd.KodKraju(company_id.country_id.code),
                Eetd.KodPocztowy(company_id.zip),
                Eetd.Miejscowosc(company_id.city),
                Eetd.Ulica(company_id.x_street_short),
                Eetd.NrDomu(company_id.x_street_short_number or 'brak'),
            )

        to_validate = {'pl_tax_office_id'}

        if company_id.country_id == self.env.ref('base.pl'):
            to_validate.update({'pl_county', 'pl_community', 'state_id'})

        for field in to_validate:
            if not company_id[field]:
                raise UserError(_('%s is not set for company.', company_id._fields[field].string))

        counter = Counter()

        jpk = Etns.JPK(
            Etns.Naglowek(
                Etns.KodFormularza('JPK_KR_PD', kodSystemowy='JPK_KR_PD (1)', wersjaSchemy='1-1'),
                Etns.WariantFormularza('1'),
                Etns.CelZlozenia(options['purpose_type']),
                Etns.DataWytworzeniaJPK(fields.Datetime.now()),
                Etns.DataOd(options['date_from']),
                Etns.DataDo(options['date_to']),
                Etns.RokDataOd(fields.Date.start_of(fields.Date.to_date(options['date_from']), 'year')),
                Etns.RokDataDo(fields.Date.end_of(fields.Date.to_date(options['date_to']), 'year')),
                Etns.DomyslnyKodWaluty(company_currency_id.name),
                Etns.KodUrzedu(company_id.pl_tax_office_id.code),
            ),
            Etns.Podmiot1(
                Etns.IdentyfikatorPodmiotu(
                    Eetd.NIP(re.sub(r'\D', '', company_id.vat)),
                    Eetd.PelnaNazwa(company_id.name[:240]),
                    *podmiot1_regon,
                ),
                Etns.Adres(podmiot1_addr),
            ),
            # Kontrahent
            *self.process_section(options=options, section=KrPdData.kontrahent),
            # ZOiS
            Etns.ZOiS(
                *self.process_section(
                    options=options,
                    section=KrPdData.zois,
                    element_name=options.get('zois_type'),
                    currency_id=company_currency_id,
                ),
            ),
            # Dziennik/KontoZapis
            *self.process_section(
                options=options,
                section=KrPdData.dziennik,
                counter=counter,
                currency_id=company_currency_id,
            ),
            Etns.Ctrl(
                Etns.C_1(counter['dziennik_lines']),
                Etns.C_2(counter['C_2']),
                Etns.C_3(counter['kontozapis_lines']),
                Etns.C_4(counter['C_4']),
                Etns.C_5(counter['C_5']),
            ),
            # RPD
            *self.process_section(options=options, section=KrPdData.rpd, currency_id=company_currency_id),
        )

        # noinspection bad-argument-type
        return etree.tostring(jpk, encoding='UTF-8', pretty_print=True)

    def transfer_xml(self, options):
        date_from = options.get('date_from')

        # noinspection PyUnresolvedReferences
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'jpk.transfer',
            'view_mode': 'form',
            'res_id': self.env['jpk.transfer']
            .create_with_document(
                {
                    'name': f'JPK KR PD {date_from}',
                    'jpk_type': 'JPKAH',
                    'file_name': f'jpk_kr_pd_{date_from}.xml',
                    'data': self.get_xml(options),
                    'document_type': 'trilab_jpk_base.jpk_kr_pd_doc_type',
                },
            )
            .id,
        }

    def generate_xml_report(self, file_data, doc_ids, options):
        file_data.write(self.get_xml(options))

    @api.model
    def _get_report_name(self):
        return _('Jednolity Plik Kontrolny - KR PD')

    def _write_cell_with_check(self, column, value, sheet, y_offset, x_offset):
        if value is not None:
            if column.is_date:
                self._write_cell(sheet, y_offset, x_offset, value, style='default_date')

            elif column.is_number:
                self._write_cell(sheet, y_offset, x_offset, float(value), style='monetary')

            else:
                self._write_cell(sheet, y_offset, x_offset, value)

    def generate_xlsx_report(self, workbook, doc_ids, options):
        data = self._get_report_data(doc_ids, options)
        sheet = workbook.add_worksheet(self._get_report_name()[:31])

        y_offset = 0

        # Set the first column width to 20
        sheet.set_column(0, 0, 20)
        sheet.set_column(2, 2, 20)
        sheet.set_column(3, 3, 50)
        sheet.set_column(4, 4, 25)
        sheet.set_column(5, 17, 15)

        for section in data['sections']:
            self._write_cell(sheet, y_offset, 0, section.title, style='title')
            y_offset += 1

            for idx, column in enumerate(section.columns):
                self._write_cell(sheet, y_offset, idx, f'{column.name} {column.label}', style='title')

            if section.sub_section:
                offset = len(section.columns)

                for idx, column in enumerate(section.sub_section.columns):
                    self._write_cell(
                        sheet,
                        y_offset,
                        offset + idx,
                        f'{column.name} {column.label}',
                        style='title',
                    )

            y_offset += 1

            for line in data['sections'][section]['lines']:
                if (sub_section := section.sub_section) and (sub_lines := line.get('lines')):
                    offset = len(section.columns)

                    for line_idx, sub_line in enumerate(sub_lines):
                        if line_idx:
                            y_offset += 1

                        for idx, column in enumerate(section.columns):
                            self._write_cell_with_check(column, line['values'][idx], sheet, y_offset, idx)

                        for idx, column in enumerate(sub_section.columns):
                            self._write_cell_with_check(column, sub_line['values'][idx], sheet, y_offset, offset + idx)

                    y_offset += 1

                else:
                    for idx, column in enumerate(section.columns):
                        self._write_cell_with_check(column, line['values'][idx], sheet, y_offset, idx)

                    y_offset += 1
