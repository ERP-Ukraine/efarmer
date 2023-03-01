# -*- coding: utf-8 -*-
# pylint: disable=protected-access

from odoo import api, models, _

_merchandise_export_code = {
    'BE': '29',
    'FR': '21',
    'NL': '7',
}

_merchandise_import_code = {
    'BE': '19',
    'FR': '11',
    'NL': '6',
}

_unknown_country_code = {
    'BE': 'QU',
    'NL': 'QV',
}

_qn_unknown_individual_vat_country_codes = ('FI', 'SE', 'SK', 'DE', 'AT')


class AccountIntrastatReport(models.AbstractModel):
    _inherit = 'account.intrastat.report'

    # This method is completely overridden
    # The standard method is here
    # enterprise/account_intrastat/models/account_intrastat_report.py
    def _get_columns_name(self, options):
        columns = [
            {'name': ''},
            {'name': _('Invoice Date'), 'class': 'date', 'style': 'text-align:center; white-space:nowrap;'},
            {'name': _('Product Name')},
            {'name': _('Country Code')},
            {'name': _('Transaction Code')},
            {'name': _('Commodity Code')},
            {'name': _('Type')},
            {'name': _('Origin Country')},
            {'name': _('Partner Name')},
            {'name': _('Partner VAT')},
        ]

        if options.get('intrastat_extended'):
            columns += [
                {'name': _('Transport Code')},
                {'name': _('Incoterm Code')},
            ]
        columns += [
            {'name': _('Weight')},
            {'name': _('Quantity')},
            {'name': _('Supplementary Units')},
            {'name': _('Value'), 'class': 'number'},
        ]
        return columns

    # This method is completely overridden
    # The standard method is here
    # enterprise/account_intrastat/models/account_intrastat_report.py
    @api.model
    def _build_query(self, date_from, date_to, journal_ids, invoice_types=None, with_vat=False):
        # triangular use cases are handled by letting the intrastat_country_id editable on
        # invoices. Modifying or emptying it allow to alter the intrastat declaration
        # accordingly to specs (https://www.nbb.be/doc/dq/f_pdf_ex/intra2017fr.pdf (§ 4.x))
        select = '''
                row_number() over () AS sequence,
                CASE WHEN inv.move_type IN ('in_invoice', 'out_refund') THEN %(import_merchandise_code)s ELSE %(export_merchandise_code)s END AS system,
                country.code AS country_code,
                country.name AS country_name,
                company_country.code AS comp_country_code,
                transaction.code AS transaction_code,
                company_region.code AS region_code,
                code.code AS commodity_code,
                inv_line.id AS id,
                prodt.id AS template_id,
                prodt.categ_id AS category_id,
                prodt.name AS prod_name,
                inv_line.product_uom_id AS uom_id,
                inv_line_uom.category_id AS uom_category_id,
                inv.id AS invoice_id,
                inv.currency_id AS invoice_currency_id,
                inv.name AS invoice_number,
                coalesce(inv.date, inv.invoice_date) AS invoice_date,
                inv.move_type AS invoice_type,
                inv_incoterm.code AS invoice_incoterm,
                comp_incoterm.code AS company_incoterm,
                inv_transport.code AS invoice_transport,
                comp_transport.code AS company_transport,
                CASE WHEN inv.move_type IN ('in_invoice', 'out_refund') THEN 'Arrival' ELSE 'Dispatch' END AS type,
                ROUND(
                    prod.weight * inv_line.quantity / (
                        CASE WHEN inv_line_uom.category_id IS NULL OR inv_line_uom.category_id = prod_uom.category_id
                        THEN inv_line_uom.factor ELSE 1 END
                    ) * (
                        CASE WHEN prod_uom.uom_type <> 'reference'
                        THEN prod_uom.factor ELSE 1 END
                    ),
                    SCALE(ref_weight_uom.rounding)
                ) AS weight,
                inv_line.quantity / (
                    CASE WHEN inv_line_uom.category_id IS NULL OR inv_line_uom.category_id = prod_uom.category_id
                    THEN inv_line_uom.factor ELSE 1 END
                ) AS quantity,
                inv_line.quantity AS line_quantity,
                CASE WHEN inv_line.price_subtotal = 0 THEN inv_line.price_unit * inv_line.quantity ELSE inv_line.price_subtotal END AS value,
                COALESCE(product_country.code, %(unknown_country_code)s) AS intrastat_product_origin_country,
                product_country.name AS intrastat_product_origin_country_name,
                CASE WHEN partner.name IS NOT NULL THEN partner.name
                     WHEN partner.name IS NULL AND partner.is_company IS FALSE THEN %(unknown_individual_vat)s
                     ELSE 'QV999999999999'
                END AS partner_name,
                CASE WHEN partner.vat IS NOT NULL THEN partner.vat
                     WHEN partner.vat IS NULL AND partner.is_company IS FALSE THEN %(unknown_individual_vat)s
                     ELSE 'QV999999999999'
                END AS partner_vat
                '''
        from_ = '''
                account_move_line inv_line
                LEFT JOIN account_move inv ON inv_line.move_id = inv.id
                LEFT JOIN account_intrastat_code transaction ON inv_line.intrastat_transaction_id = transaction.id
                LEFT JOIN res_company company ON inv.company_id = company.id
                LEFT JOIN account_intrastat_code company_region ON company.intrastat_region_id = company_region.id
                LEFT JOIN res_partner partner ON inv_line.partner_id = partner.id
                LEFT JOIN res_partner comp_partner ON company.partner_id = comp_partner.id
                LEFT JOIN res_country country ON inv.intrastat_country_id = country.id
                LEFT JOIN res_country company_country ON comp_partner.country_id = company_country.id
                INNER JOIN product_product prod ON inv_line.product_id = prod.id
                LEFT JOIN product_template prodt ON prod.product_tmpl_id = prodt.id
                LEFT JOIN account_intrastat_code code ON code.id = COALESCE(prod.intrastat_variant_id, prodt.intrastat_id)
                LEFT JOIN uom_uom inv_line_uom ON inv_line.product_uom_id = inv_line_uom.id
                LEFT JOIN uom_uom prod_uom ON prodt.uom_id = prod_uom.id
                LEFT JOIN account_incoterms inv_incoterm ON inv.invoice_incoterm_id = inv_incoterm.id
                LEFT JOIN account_incoterms comp_incoterm ON company.incoterm_id = comp_incoterm.id
                LEFT JOIN account_intrastat_code inv_transport ON inv.intrastat_transport_mode_id = inv_transport.id
                LEFT JOIN account_intrastat_code comp_transport ON company.intrastat_transport_mode_id = comp_transport.id
                LEFT JOIN res_country product_country ON product_country.id = inv_line.intrastat_product_origin_country_id
                LEFT JOIN res_country partner_country ON partner.country_id = partner_country.id AND partner_country.intrastat IS TRUE
                LEFT JOIN uom_uom ref_weight_uom on ref_weight_uom.category_id = %(weight_category_id)s and ref_weight_uom.uom_type = 'reference'
                '''
        where = '''
                inv.state = 'posted'
                AND inv_line.display_type IS NULL
                AND (NOT inv_line.price_subtotal = 0 OR inv_line.price_unit * inv_line.quantity != 0)
                AND inv.company_id = %(company_id)s
                AND company_country.id != country.id
                AND country.intrastat = TRUE AND (country.code != 'GB' OR inv.date < '2021-01-01')
                AND coalesce(inv.date, inv.invoice_date) >= %(date_from)s
                AND coalesce(inv.date, inv.invoice_date) <= %(date_to)s
                AND prodt.type != 'service'
                AND inv.journal_id IN %(journal_ids)s
                AND inv.move_type IN %(invoice_types)s
                AND NOT inv_line.exclude_from_invoice_tab
                '''
        order = 'inv.invoice_date DESC, inv_line.id'
        params = {
            'company_id': self.env.company.id,
            'import_merchandise_code': _merchandise_import_code.get(self.env.company.country_id.code, '29'),
            'export_merchandise_code': _merchandise_export_code.get(self.env.company.country_id.code, '19'),
            'date_from': date_from,
            'date_to': date_to,
            'journal_ids': tuple(journal_ids),
            'weight_category_id': self.env['ir.model.data']._xmlid_to_res_id('uom.product_uom_categ_kgm'),
            'unknown_individual_vat': 'QN999999999999' if self.env.company.country_id.code in _qn_unknown_individual_vat_country_codes else 'QV999999999999',
            'unknown_country_code': _unknown_country_code.get(self.env.company.country_id.code, 'QV'),
        }
        if with_vat:
            where += ' AND partner.vat IS NOT NULL '
        if invoice_types:
            params['invoice_types'] = tuple(invoice_types)
        else:
            params['invoice_types'] = ('out_invoice', 'out_refund', 'in_invoice', 'in_refund')
        query = {
            'select': select,
            'from': from_,
            'where': where,
            'order': order,
        }
        return query, params

    # This method is completely overridden
    # The standard method is here
    # enterprise/account_intrastat/models/account_intrastat_report.py
    @api.model
    def _create_intrastat_report_line(self, options, vals):
        # This is so that full country names are displayed when in the UI, and the 2-digit iso codes are used when 'code' is in the options
        country_column = 'country_code' if options.get('country_format') == 'code' else 'country_name'
        origin_country_column = 'intrastat_product_origin_country' if options.get(
            'country_format') == 'code' else 'intrastat_product_origin_country_name'

        columns = [{'name': c} for c in [
            str(vals['invoice_date']) or '',
            vals['prod_name'] or '',
            vals[country_column],
            vals['transaction_code'],
            vals['commodity_code'] or '',
            vals['type'],
            vals[origin_country_column],
            vals['partner_name'],
            vals['partner_vat'],
        ]]
        if options.get('intrastat_extended'):
            columns += [{'name': c} for c in [
                vals['invoice_transport'] or vals['company_transport'] or '',
                vals['invoice_incoterm'] or vals['company_incoterm'] or '',
            ]]
        columns += [{'name': c} for c in [
            vals['weight'],
            vals['line_quantity'],
            vals['supplementary_units'],
            self.format_value(vals['value']),
        ]]

        return {
            'id': vals['id'],
            'caret_options': 'account.move',
            'model': 'account.move.line',
            'name': vals['invoice_number'],
            'columns': columns,
            'level': 2,
        }
