import json
import logging
import math
from datetime import datetime, timezone

import pytz
from lxml import etree
from odoo.tools import float_is_zero, float_repr

from odoo import _, api, fields, models, tools

from .ksef_client import InvoiceBatchExportPendingError, KsefClientError, KsefInvoiceBatchExportError

_logger = logging.getLogger(__name__)

KSEF_CODE = 'ksef'
RELEASE_INFO = 'Trilab KSeF - trilab_ksef'

NS = {
    'tns': 'http://crd.gov.pl/wzor/2025/06/25/13775/',
    'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
    'etd': 'http://crd.gov.pl/xml/schematy/dziedzinowe/mf/2022/01/05/eD/DefinicjeTypy/',
}


class AccountEdiFormat(models.Model):
    _inherit = 'account.edi.format'

    def _is_compatible_with_journal(self, journal):
        self.ensure_one()

        if self.code != KSEF_CODE:
            return super()._is_compatible_with_journal(journal)

        return journal.country_code == 'PL' and journal.type == 'sale'

    def _is_enabled_by_default_on_journal(self, journal):
        self.ensure_one()

        if self.code == KSEF_CODE:
            return False

        return super()._is_enabled_by_default_on_journal(journal)

    def _check_move_configuration(self, move):
        self.ensure_one()
        errors = super()._check_move_configuration(move)

        if self.code != KSEF_CODE:
            return errors

        return errors + self._x_ksef_move_configuration(move)

    def _needs_web_services(self):
        self.ensure_one()
        return self.code == KSEF_CODE or super()._needs_web_services()

    def _x_ksef_applicable(self, move_id):
        return (
            self.code == KSEF_CODE
            and move_id.x_get_is_poland()
            and move_id.country_code == 'PL'
            and move_id.is_sale_document()
            and (move_id.partner_id.is_company or move_id.partner_id.vat)
        )

    def _is_required_for_invoice(self, invoice):
        self.ensure_one()

        if self.code != KSEF_CODE:
            return super()._is_required_for_invoice(invoice)

        return self._x_ksef_applicable(invoice)

    def _support_batching(self, move, state, company):
        if self.code == KSEF_CODE:
            return True

        return super()._support_batching(move=move, state=state, company=company)

    def _get_invoice_edi_content(self, move):
        if self.code == KSEF_CODE:
            return self._x_ksef_content_edi(move)

        return super()._get_invoice_edi_content(move)

    def _post_invoice_edi(self, invoices):
        self.ensure_one()

        if self.code != KSEF_CODE:
            return super()._post_invoice_edi(invoices)

        return self.x_ksef_post_edi(invoices)

    @api.model
    def _x_ksef_move_configuration(self, move_id):
        errors = []

        if not move_id.company_id.x_ksef_settings_id:
            errors.append(_('- KSeF settings not configured for company: %s', move_id.company_id.name))

        if not move_id.company_id.x_ksef_plain_token:
            errors.append(_('- KSeF Token not configured for company: %s', move_id.company_id.name))

        if not move_id.x_is_poland:
            errors.append(_('- Trilab Invoice is not enabled for company: %s', move_id.company_id.name))

        if not move_id.x_invoice_sale_date:
            errors.append(_('- Sale/Currency Date not filled'))

        if not move_id.company_id.vat:
            errors.append(_('- Tax ID not filled for company: %s', move_id.company_id.name))

        if not move_id.company_id.country_id:
            errors.append(_('- Country not filled for company: %s', move_id.company_id.name))

        if not all((move_id.company_id.street, move_id.company_id.zip, move_id.company_id.city)):
            errors.append(
                _(
                    '- Address info is not fully filled for company: %s\nRequired: Street, Zip, City',
                    move_id.company_id.name,
                )
            )

        if not move_id.partner_id.country_id:
            errors.append(_('- Country not filled for partner: %s', move_id.partner_id.name))

        if not all((move_id.partner_id.street, move_id.partner_id.zip, move_id.partner_id.city)):
            errors.append(
                _(
                    '- Address info is not fully filled for partner: %s\nRequired: Street, Zip, City',
                    move_id.partner_id.name,
                )
            )

        if (
            move_id.x_ksef_p_pmarzy
            and len(
                list(
                    filter(
                        None,
                        (
                            move_id.x_ksef_p_pmarzy_2,
                            move_id.x_ksef_p_pmarzy_3_1,
                            move_id.x_ksef_p_pmarzy_3_2,
                            move_id.x_ksef_p_pmarzy_3_3,
                        ),
                    )
                )
            )
            != 1
        ):
            errors.append(
                _(
                    '- P_PMarzy selected. Only one of these fields must be selected: '
                    'P_PMarzy_2, P_PMarzy_3_1, P_PMarzy_3_2, P_PMarzy_3_3'
                )
            )

        if (
            move_id.x_ksef_p_19
            and len(list(filter(None, (move_id.x_ksef_p_19a, move_id.x_ksef_p_19b, move_id.x_ksef_p_19c)))) != 1
        ):
            errors.append(_('- P_19 selected. Only one of these fields must be selected: P_19A, P_19B, P_19C'))

        invoice_line_ids = move_id.x_ksef_get_invoice_line_ids()

        if any(not _l_id.tax_ids for _l_id in invoice_line_ids):
            errors.append(_('- No taxes assigned to invoice lines'))

        if False in invoice_line_ids.tax_ids.mapped('x_ksef_amount'):
            errors.append(_('- KSeF Tax Amount Mapping must be set for taxes used in invoice lines'))

        if any(
            _adv_inv_id.x_ksef_invoice_reference and not _adv_inv_id.x_pl_ksef_invoice_number
            for _adv_inv_id in (move_id.advance_invoices_ids - move_id)
        ):
            errors.append(_('- KSeF Invoice Number is missing for some advance invoices'))

        if (
            move_id.reversed_entry_id.x_ksef_invoice_reference
            and not move_id.reversed_entry_id.x_pl_ksef_invoice_number
        ):
            errors.append(_('- KSeF Invoice Number is missing for reversed entry'))

        if move_id.move_type == 'out_refund':
            if not move_id.reversed_entry_id:
                errors.append(_('- Reversed entry is missing for refund invoice'))

            if len(move_id.original_invoice_line_ids) != len(move_id.corrected_invoice_line_ids):
                errors.append(_('- Number of corrected invoice lines does not match number of original invoice lines'))

        if (
            sum(
                [
                    move_id.x_pl_vat_wsto_ee,
                    move_id.x_pl_vat_ied,
                    move_id.x_pl_vat_tt_d,
                    move_id.x_pl_vat_i42,
                    move_id.x_pl_vat_i63,
                    move_id.x_pl_vat_b_spv,
                    move_id.x_pl_vat_b_spv_dostawa,
                    move_id.x_pl_vat_b_mpv_prowizja,
                ]
            )
            > 1
        ):
            errors.append(_('- Too many procedures selected. Please select only one or none.'))

        return errors

    @api.model
    def x_ksef_post_edi(self, invoice_ids) -> dict:
        if len(invoice_ids) == 1:
            return self._x_ksef_post_interactive_edi(invoice_ids)

        elif len(invoice_ids) > 1:
            return self._x_ksef_post_batch_edi(invoice_ids)

        return {}

    @api.model
    def _x_ksef_post_batch_edi(self, invoice_ids):
        invoice_xml_contents = [
            (invoice_id.x_ksef_get_invoice_file_name(), self._x_ksef_content_edi(invoice_id))
            for invoice_id in invoice_ids
        ]

        try:
            client = invoice_ids.company_id.x_ksef_get_authenticated_client()

            session_reference = client.start_invoice_batch_import(
                invoices=invoice_xml_contents,
            )
            client.close_invoice_batch_import()

        except KsefClientError as error:
            return {
                invoice_id: {
                    'error': str(error),
                    'blocking_level': 'error',
                }
                for invoice_id in invoice_ids
            }

        invoice_ids.update(
            {
                'x_ksef_last_invoice_status': None,
                'x_ksef_session_reference': session_reference,
                'x_ksef_session_type': 'batch',
            }
        )

        return {
            invoice_id: {
                'success': True,
                'attachment': self.env['ir.attachment'].create(
                    {
                        'name': file_name,
                        'raw': file_content,
                        'res_model': 'account.move',
                        'res_id': invoice_id.id,
                        'mimetype': 'application/xml',
                    }
                ),
            }
            for invoice_id, (file_name, file_content) in zip(invoice_ids, invoice_xml_contents, strict=False)
        }

    @api.model
    def _x_ksef_post_interactive_edi(self, invoice_id):
        invoice_xml_content = self._x_ksef_content_edi(invoice_id)

        try:
            client = invoice_id.company_id.x_ksef_get_authenticated_client()
            session_reference, _session_valid_until = client.open_interactive_session()
            ksef_invoice_reference = client.send_invoice(invoice_xml_content)
            client.close_interactive_session()

        except KsefClientError as error:
            return {
                invoice_id: {
                    'error': str(error),
                    'blocking_level': 'error',
                }
            }

        invoice_id.update(
            {
                'x_ksef_last_invoice_status': None,
                'x_ksef_invoice_reference': ksef_invoice_reference,
                'x_ksef_session_reference': session_reference,
                'x_ksef_session_type': 'interactive',
            }
        )

        return {
            invoice_id: {
                'success': True,
                'attachment': self.env['ir.attachment']
                .with_context(tools.clean_context(self.env.context))
                .create(
                    {
                        'name': f'{ksef_invoice_reference}.xml',
                        'raw': invoice_xml_content,
                        'res_model': 'account.move',
                        'res_id': invoice_id.id,
                        'mimetype': 'application/xml',
                    }
                ),
            }
        }

    def _x_ksef_content_edi(self, invoice_id):
        return self._x_ksef_get_invoice_xml(invoice_data=self._x_ksef_get_invoice_data(invoice_id))

    @api.model
    def _x_ksef_get_invoice_type(self, invoice_id):
        if invoice_id.move_type == 'out_invoice':
            if invoice_id._is_downpayment():
                return 'ZAL'

            if invoice_id.advance_invoices_ids:
                return 'ROZ'

            return 'VAT'

        if invoice_id.move_type == 'out_refund':
            if invoice_id._is_downpayment():
                return 'KOR_ZAL'

            if invoice_id.advance_invoices_ids:
                return 'KOR_ROZ'

            return 'KOR'

        return None

    @api.model
    def _x_ksef_get_seller(self, invoice_id):
        return {
            'nip': invoice_id.company_id.partner_id.x_get_pl_vat(raise_exception=True),
            'name': invoice_id.company_id.name,
            'address': {
                'country_code': invoice_id.company_id.country_id.code,
                'address_line_1': ' '.join(
                    (invoice_id.company_id.street, invoice_id.company_id.zip, invoice_id.company_id.city)
                ),
                'address_line_2': invoice_id.company_id.street2 or None,
            },
        }

    @api.model
    def _x_ksef_get_buyer(self, invoice_id):
        return {
            'name': invoice_id.partner_id.name,
            'address': {
                'country_code': invoice_id.partner_id.country_id.code,
                'address_line_1': ' '.join(
                    filter(None, (invoice_id.partner_id.street, invoice_id.partner_id.zip, invoice_id.partner_id.city))
                ),
                'address_line_2': invoice_id.partner_id.street2 or None,
            },
            'nip': invoice_id.partner_id.x_get_pl_vat(raise_exception=True),
            'vat_eu': (vat_eu := invoice_id.partner_id.x_get_eu_vat()) and vat_eu[2:],
            'vat_eu_code': invoice_id.partner_id.x_get_eu_vat_country(),
            'tin': not vat_eu and invoice_id.partner_id.company_registry,
        }

    @api.model
    def _x_ksef_get_invoice_procedure(self, invoice_id):
        if invoice_id.x_pl_vat_wsto_ee:
            return 'WSTO_EE'
        if invoice_id.x_pl_vat_ied:
            return 'IED'
        if invoice_id.x_pl_vat_tt_d:
            return 'TT_D'
        if invoice_id.x_pl_vat_i42:
            return 'I_42'
        if invoice_id.x_pl_vat_i63:
            return 'I_63'
        if invoice_id.x_pl_vat_b_spv:
            return 'B_SPV'
        if invoice_id.x_pl_vat_b_spv_dostawa:
            return 'B_SPV_DOSTAWA'
        if invoice_id.x_pl_vat_b_mpv_prowizja:
            return 'B_MPV_PROWIZJA'
        return None

    @api.model
    def _x_ksef_amount_repr(self, value):
        return float_repr(value=value, precision_digits=2)

    @api.model
    def _x_ksef_get_invoice_lines(self, invoice_id):
        res = []

        enable_barcodes = invoice_id.company_id.x_ksef_enable_barcodes

        invoice_line_ids = invoice_id.x_ksef_get_invoice_line_ids()

        for index, line_id in enumerate(invoice_line_ids, start=1):
            is_corrected_line = line_id.corrected_line
            quantity = line_id.quantity if not is_corrected_line else line_id.x_quantity_reverse

            taxes_res = line_id.tax_ids.compute_all(
                line_id.price_unit,
                quantity=math.copysign(1.0, quantity),
                currency=line_id.currency_id,
                product=line_id.product_id,
                partner=line_id.partner_id,
                is_refund=line_id.move_id.move_type in ('in_refund', 'out_refund'),
            )
            price_unit_untaxed = taxes_res['total_excluded']
            price_unit = taxes_res['total_included']

            if invoice_id.x_ksef_invoice_date_applicability == 'itemized':
                # field in account_accountant - enterprise version
                line_date = (
                    getattr(line_id, 'deferred_end_date', None) or line_id.move_id.x_invoice_sale_date
                ).isoformat()
            else:
                line_date = None

            res.append(
                {
                    'index': str(index),
                    'uom_name': (
                        line_id.product_uom_id.with_context(lang=invoice_id.partner_id.lang).name
                        if line_id.product_uom_id
                        else None
                    ),
                    'name': line_id.name,
                    'quantity': float_repr(
                        quantity,
                        self.env['decimal.precision'].precision_get('Product Unit of Measure'),
                    ),
                    'discount': self._x_ksef_amount_repr(line_id.discount) if line_id.discount else None,
                    'price_subtotal': self._x_ksef_amount_repr(
                        line_id.price_subtotal if not is_corrected_line else line_id.x_price_subtotal_reverse
                    ),
                    'price_total': self._x_ksef_amount_repr(
                        line_id.price_total if not is_corrected_line else line_id.x_price_total_reverse
                    ),
                    'price_unit_untaxed': self._x_ksef_amount_repr(price_unit_untaxed),
                    'price_unit': self._x_ksef_amount_repr(price_unit),
                    'tax_rate': fields.first(line_id.tax_ids).x_ksef_amount,
                    'barcode': line_id.product_id.barcode if enable_barcodes else None,
                    'gtu': line_id.x_pl_vat_gtu.name,
                    'is_corrected': is_corrected_line,
                    'date': line_date,
                    'procedure': self._x_ksef_get_invoice_procedure(invoice_id),
                }
            )

        return res

    @api.model
    def _x_ksef_get_order_amount_total(self, invoice_id):
        order_ids = invoice_id.line_ids.sale_line_ids.order_id

        if not order_ids:
            return None

        return self._x_ksef_amount_repr(sum(order_ids.mapped('amount_total')))

    @api.model
    def _x_ksef_get_order_lines(self, invoice_id):
        res = []

        enable_barcodes = invoice_id.company_id.x_ksef_enable_barcodes

        order_line_ids = invoice_id.line_ids.sale_line_ids.order_id.order_line.filtered(
            lambda _l_id: not _l_id.display_type and not _l_id.is_downpayment
        )

        if invoice_id.company_id.x_ksef_enable_ignore_zero_amount_lines:
            order_line_ids = order_line_ids.filtered(
                lambda _l_id: (
                    not float_is_zero(_l_id.price_unit, self.env['decimal.precision'].precision_get('Product Price'))
                )
            )

        for index, line_id in enumerate(order_line_ids, start=1):
            res.append(
                {
                    'index': str(index),
                    'uom_name': (
                        line_id.product_uom.with_context(lang=invoice_id.partner_id.lang).name
                        if line_id.product_uom
                        else None
                    ),
                    'name': line_id.name,
                    'quantity': float_repr(
                        line_id.product_uom_qty, self.env['decimal.precision'].precision_get('Product Unit of Measure')
                    ),
                    'price_subtotal': self._x_ksef_amount_repr(line_id.price_subtotal),
                    'price_unit_untaxed': self._x_ksef_amount_repr(
                        (
                            line_id.currency_id.round(line_id.price_subtotal / line_id.product_uom_qty)
                            if line_id.product_uom_qty
                            else 0.0
                        ),
                    ),
                    'price_tax': self._x_ksef_amount_repr(line_id.price_tax),
                    'tax_rate': fields.first(line_id.tax_id).x_ksef_amount,
                    'barcode': line_id.product_id.barcode if enable_barcodes else None,
                }
            )

        return res

    @api.model
    def _x_ksef_get_orders_data(self, invoice_id):
        return [
            {
                'order_date': _order_id.date_order.date().isoformat(),
                'order_name': _order_id.name,
            }
            for _order_id in invoice_id.line_ids.sale_line_ids.order_id
        ]

    @api.model
    def _x_ksef_get_invoice_payments_data(self, invoice_id):
        if invoice_id.invoice_payment_term_id.x_ksef_payment_state_mapping == 'paid':
            return {
                'is_paid': True,
                'is_partial': False,
                'payments': [{'date': invoice_id.invoice_date.isoformat()}],
            }

        elif invoice_id.invoice_payment_term_id.x_ksef_payment_state_mapping == 'not_paid':
            return {
                'is_paid': False,
                'is_partial': False,
                'payments': [],
            }

        payments_content = (
            invoice_id.invoice_payments_widget and json.loads(invoice_id.invoice_payments_widget) or {}
        ).get('content', [])

        return {
            'is_paid': invoice_id.payment_state == 'paid',
            'is_partial': invoice_id.payment_state == 'partial',
            'payments': [
                {
                    'amount': self._x_ksef_amount_repr(val['amount']),
                    'date': val['date'].isoformat(),
                }
                for val in payments_content
            ],
        }

    @api.model
    def _x_ksef_get_invoice_currency_rate(self, invoice_id):
        if invoice_id.currency_id == invoice_id.company_currency_id:
            return None

        if not invoice_id.company_currency_id.is_zero(invoice_id.x_currency_rate):
            return float_repr(invoice_id.x_currency_rate, precision_digits=4)

        return float_repr(
            abs(invoice_id.company_currency_id.round(invoice_id.amount_total_signed / invoice_id.amount_total)),
            precision_digits=4,
        )

    @api.model
    def _x_ksef_get_tax_base_amount(self, invoice_id, tax_amounts, field='tax_group_base_amount'):
        tax_groups = invoice_id.invoice_line_ids.tax_ids.filtered_domain(
            [('amount', 'in', tax_amounts)]
        ).tax_group_id.ids

        tax_totals = json.loads(invoice_id.tax_totals_json)

        if not tax_totals['groups_by_subtotal'] or not tax_groups:
            return self._x_ksef_amount_repr(0)

        return self._x_ksef_amount_repr(
            sum(
                group[field]
                for groups in tax_totals['groups_by_subtotal'].values()
                for group in groups
                if group['tax_group_id'] in tax_groups
            ),
        )

    @api.model
    def _x_ksef_get_tax_amount(self, invoice_id, tax_amounts, field='tax_group_amount'):
        return self._x_ksef_get_tax_base_amount(invoice_id, tax_amounts, field=field)

    @api.model
    def _x_ksef_get_zero_tax_base_amount(self, invoice_id, ksef_tax_amount):
        return self._x_ksef_amount_repr(
            abs(
                sum(
                    invoice_id.line_ids.filtered(
                        lambda _l_id: (
                            (tax_id := fields.first(_l_id.tax_ids)) and tax_id.x_ksef_amount == ksef_tax_amount
                        )
                    ).mapped('amount_currency')
                )
            ),
        )

    @api.model
    def _x_ksef_get_invoice_data(self, invoice_id):
        return {
            'seller': self._x_ksef_get_seller(invoice_id),
            'buyer': self._x_ksef_get_buyer(invoice_id),
            'currency_code': invoice_id.currency_id.name,
            'p_1': invoice_id.invoice_date and invoice_id.invoice_date.isoformat(),
            'p_2': invoice_id.name,
            'p_6': invoice_id.x_invoice_sale_date and invoice_id.x_invoice_sale_date.isoformat(),
            'p_13_1': self._x_ksef_get_tax_base_amount(invoice_id, (22, 23)),
            'p_14_1': self._x_ksef_get_tax_amount(invoice_id, (22, 23)),
            'p_14_1w': (
                self._x_ksef_get_tax_amount(invoice_id, (22, 23), field='x_tax_group_amount_in_pln')
                if invoice_id.currency_id != invoice_id.company_currency_id
                else None
            ),
            'p_13_2': self._x_ksef_get_tax_base_amount(invoice_id, (7, 8)),
            'p_14_2': self._x_ksef_get_tax_amount(invoice_id, (7, 8)),
            'p_14_2w': (
                self._x_ksef_get_tax_amount(invoice_id, (7, 8), field='x_tax_group_amount_in_pln')
                if invoice_id.currency_id != invoice_id.company_currency_id
                else None
            ),
            'p_13_3': self._x_ksef_get_tax_base_amount(invoice_id, (5,)),
            'p_14_3': self._x_ksef_get_tax_amount(invoice_id, (5,)),
            'p_14_3w': (
                self._x_ksef_get_tax_amount(invoice_id, (5,), field='x_tax_group_amount_in_pln')
                if invoice_id.currency_id != invoice_id.company_currency_id
                else None
            ),
            'p_13_6_1': self._x_ksef_get_zero_tax_base_amount(invoice_id, ksef_tax_amount='0 KR'),
            'p_13_6_2': self._x_ksef_get_zero_tax_base_amount(invoice_id, ksef_tax_amount='0 WDT'),
            'p_13_6_3': self._x_ksef_get_zero_tax_base_amount(invoice_id, ksef_tax_amount='0 EX'),
            'p_13_7': self._x_ksef_get_zero_tax_base_amount(invoice_id, ksef_tax_amount='zw'),
            'p_13_8': self._x_ksef_get_zero_tax_base_amount(invoice_id, ksef_tax_amount='np I'),
            'p_13_9': self._x_ksef_get_zero_tax_base_amount(invoice_id, ksef_tax_amount='np II'),
            'p_13_10': self._x_ksef_get_zero_tax_base_amount(invoice_id, ksef_tax_amount='oo'),
            'p_15': self._x_ksef_amount_repr(json.loads(invoice_id.tax_totals_json)['amount_total']),
            'currency_rate': self._x_ksef_get_invoice_currency_rate(invoice_id),
            'p_16': invoice_id.x_ksef_p_16,
            'p_17': invoice_id.x_ksef_p_17,
            'p_18': invoice_id.x_pl_vat_reverse_charge,
            'p_18a': invoice_id.x_pl_vat_mpp,
            'p_19': invoice_id.x_ksef_p_19,
            'p_19a': invoice_id.x_ksef_p_19 and invoice_id.x_ksef_p_19a,
            'p_19b': invoice_id.x_ksef_p_19 and invoice_id.x_ksef_p_19b,
            'p_19c': invoice_id.x_ksef_p_19 and invoice_id.x_ksef_p_19c,
            'p_22n': 1,
            'p_23': invoice_id.x_ksef_p_23,
            'p_pmarzy': invoice_id.x_ksef_p_pmarzy,
            'p_pmarzy_2': invoice_id.x_ksef_p_pmarzy and invoice_id.x_ksef_p_pmarzy_2,
            'p_pmarzy_3_1': invoice_id.x_ksef_p_pmarzy and invoice_id.x_ksef_p_pmarzy_3_1,
            'p_pmarzy_3_2': invoice_id.x_ksef_p_pmarzy and invoice_id.x_ksef_p_pmarzy_3_2,
            'p_pmarzy_3_3': invoice_id.x_ksef_p_pmarzy and invoice_id.x_ksef_p_pmarzy_3_3,
            'invoice_type': self._x_ksef_get_invoice_type(invoice_id),
            'lines': self._x_ksef_get_invoice_lines(invoice_id),
            'order_amount_total': self._x_ksef_get_order_amount_total(invoice_id),
            'order_lines': self._x_ksef_get_order_lines(invoice_id),
            'orders_data': self._x_ksef_get_orders_data(invoice_id),
            'invoice_ref': invoice_id.ref or invoice_id.invoice_origin,
            'price_include_tax': fields.first(invoice_id.invoice_line_ids.tax_ids).price_include,
            'invoice_id': invoice_id,
            'invoice_date_due': invoice_id.invoice_date_due and invoice_id.invoice_date_due.isoformat(),
            'payment_term_type': invoice_id.invoice_payment_term_id.x_ksef_payment_term_type,
            'partner_bank': (
                {
                    'acc_number': invoice_id.partner_bank_id.sanitized_acc_number,
                    'bank_bic': invoice_id.partner_bank_id.bank_bic,
                    'bank_name': invoice_id.partner_bank_id.bank_name,
                }
                if invoice_id.partner_bank_id
                else None
            ),
            'invoice_narration': invoice_id.narration.striptags().strip() if invoice_id.narration else None,
            'advance_invoices': [
                {
                    'name': _adv_inv_id.name,
                    'ksef_number': _adv_inv_id.x_pl_ksef_invoice_number,
                }
                for _adv_inv_id in invoice_id.advance_invoices_ids
            ],
            'corrected_invoice': (
                {
                    'name': invoice_id.reversed_entry_id.name,
                    'ksef_number': invoice_id.reversed_entry_id.x_pl_ksef_invoice_number,
                    'invoice_date': invoice_id.reversed_entry_id.invoice_date.isoformat(),
                    'reason': invoice_id.ref,
                }
                if invoice_id.reversed_entry_id
                else None
            ),
            'fp': invoice_id.x_pl_vat_typ_dokumentu == 'FP',
            'tp': invoice_id.x_pl_vat_tp,
            'payments_data': self._x_ksef_get_invoice_payments_data(invoice_id),
        }

    @api.model
    def _x_ksef_create_element(self, parent, tns, name, text=None, **attrs):
        element = etree.SubElement(parent, etree.QName(tns, name), attrib=attrs)

        if text is not None:
            element.text = str(text)

        return element

    @api.model
    def _x_ksef_prepend_element(self, parent, tns, name, text=None, **attrs):
        element = etree.Element(etree.QName(tns, name), attrib=attrs)

        if text is not None:
            element.text = str(text)

        parent.insert(0, element)

        return element

    @api.model
    def _x_ksef_create_conditional_element(self, parent, tns, name, value):
        if value:
            return self._x_ksef_create_element(parent, tns, name, text=value)

        return None

    @api.model
    def _x_ksef_bool_to_numeric(self, value):
        return '1' if value else '2'

    @api.model
    def _x_ksef_build_header(self, parent_el, tns):
        header_el = self._x_ksef_create_element(parent_el, tns, 'Naglowek')

        self._x_ksef_create_element(
            header_el, tns, 'KodFormularza', text='FA', kodSystemowy='FA (3)', wersjaSchemy='1-0E'
        )

        self._x_ksef_create_element(header_el, tns, 'WariantFormularza', text='3')
        self._x_ksef_create_element(header_el, tns, 'DataWytworzeniaFa', text=datetime.now(tz=pytz.UTC).isoformat())
        self._x_ksef_create_element(header_el, tns, 'SystemInfo', text=RELEASE_INFO)

    @api.model
    def _x_ksef_build_seller(self, invoice_data, parent_el, tns):
        seller_el = self._x_ksef_create_element(parent_el, tns, 'Podmiot1')

        seller_info_el = self._x_ksef_create_element(seller_el, tns, 'DaneIdentyfikacyjne')
        self._x_ksef_create_element(seller_info_el, tns, 'NIP', text=invoice_data['seller']['nip'])
        self._x_ksef_create_element(seller_info_el, tns, 'Nazwa', text=invoice_data['seller']['name'])

        seller_address_el = self._x_ksef_create_element(seller_el, tns, 'Adres')
        self._x_ksef_create_element(
            seller_address_el, tns, 'KodKraju', text=invoice_data['seller']['address']['country_code']
        )
        self._x_ksef_create_element(
            seller_address_el, tns, 'AdresL1', text=invoice_data['seller']['address']['address_line_1']
        )
        self._x_ksef_create_conditional_element(
            seller_address_el, tns, 'AdresL2', value=invoice_data['seller']['address']['address_line_2']
        )

    @api.model
    def _x_ksef_build_buyer(self, invoice_data, parent_el, tns):
        buyer_el = self._x_ksef_create_element(parent_el, tns, 'Podmiot2')

        buyer_info_el = self._x_ksef_create_element(buyer_el, tns, 'DaneIdentyfikacyjne')

        if invoice_data['buyer']['nip']:
            self._x_ksef_create_element(buyer_info_el, tns, 'NIP', text=invoice_data['buyer']['nip'])

        elif invoice_data['buyer']['vat_eu']:
            self._x_ksef_create_element(buyer_info_el, tns, 'KodUE', text=invoice_data['buyer']['vat_eu_code'])
            self._x_ksef_create_element(buyer_info_el, tns, 'NrVatUE', text=invoice_data['buyer']['vat_eu'])

        elif invoice_data['buyer']['tin']:
            self._x_ksef_create_element(
                buyer_info_el, tns, 'KodKraju', text=invoice_data['buyer']['address']['country_code']
            )
            self._x_ksef_create_element(buyer_info_el, tns, 'NrID', text=invoice_data['buyer']['tin'])

        else:
            self._x_ksef_create_element(buyer_info_el, tns, 'BrakID', text='1')

        self._x_ksef_create_element(buyer_info_el, tns, 'Nazwa', text=invoice_data['buyer']['name'])

        buyer_address_el = self._x_ksef_create_element(buyer_el, tns, 'Adres')
        self._x_ksef_create_element(
            buyer_address_el, tns, 'KodKraju', text=invoice_data['buyer']['address']['country_code']
        )
        self._x_ksef_create_element(
            buyer_address_el, tns, 'AdresL1', text=invoice_data['buyer']['address']['address_line_1']
        )
        self._x_ksef_create_conditional_element(
            buyer_address_el, tns, 'AdresL2', value=invoice_data['buyer']['address']['address_line_2']
        )

        self._x_ksef_create_element(buyer_el, tns, 'JST', text='2')
        self._x_ksef_create_element(buyer_el, tns, 'GV', text='2')

    @api.model
    def _x_ksef_build_fa_core(self, invoice_data, fa_el, tns):
        self._x_ksef_create_element(fa_el, tns, 'KodWaluty', text=invoice_data['currency_code'])
        self._x_ksef_create_element(fa_el, tns, 'P_1', text=invoice_data['p_1'])
        self._x_ksef_create_element(fa_el, tns, 'P_2', text=invoice_data['p_2'])
        self._x_ksef_create_element(fa_el, tns, 'P_6', text=invoice_data['p_6'])

        for tax_i in range(1, 4):
            self._x_ksef_create_element(fa_el, tns, f'P_13_{tax_i}', text=invoice_data[f'p_13_{tax_i}'])
            self._x_ksef_create_element(fa_el, tns, f'P_14_{tax_i}', text=invoice_data[f'p_14_{tax_i}'])

            self._x_ksef_create_conditional_element(fa_el, tns, f'P_14_{tax_i}W', value=invoice_data[f'p_14_{tax_i}w'])

        for zero_tax in ('P_13_6_1', 'P_13_6_2', 'P_13_6_3', 'P_13_7', 'P_13_8', 'P_13_9', 'P_13_10'):
            self._x_ksef_create_element(fa_el, tns, zero_tax, text=invoice_data[zero_tax.lower()])

        self._x_ksef_create_element(fa_el, tns, 'P_15', text=invoice_data['p_15'])

    @api.model
    def _x_ksef_build_annotations(self, invoice_data, fa_el, tns):
        annotations_el = self._x_ksef_create_element(fa_el, tns, 'Adnotacje')

        for annotation in ('P_16', 'P_17', 'P_18', 'P_18A'):
            self._x_ksef_create_element(
                annotations_el, tns, annotation, text=self._x_ksef_bool_to_numeric(invoice_data[annotation.lower()])
            )

        exemptions_el = self._x_ksef_create_element(annotations_el, tns, 'Zwolnienie')

        if invoice_data['p_19']:
            self._x_ksef_create_element(exemptions_el, tns, 'P_19', text='1')

            for key in ('P_19A', 'P_19B', 'P_19C'):
                if invoice_data[key.lower()]:
                    self._x_ksef_create_element(exemptions_el, tns, key, text=invoice_data[key.lower()])
                    break
        else:
            self._x_ksef_create_element(exemptions_el, tns, 'P_19N', text='1')

        new_means_of_transport_el = self._x_ksef_create_element(annotations_el, tns, 'NoweSrodkiTransportu')

        if invoice_data['p_22n']:
            self._x_ksef_create_element(new_means_of_transport_el, tns, 'P_22N', text='1')

        self._x_ksef_create_element(
            annotations_el, tns, 'P_23', text=self._x_ksef_bool_to_numeric(invoice_data['p_23'])
        )

        margins_el = self._x_ksef_create_element(annotations_el, tns, 'PMarzy')

        if invoice_data['p_pmarzy']:
            self._x_ksef_create_element(margins_el, tns, 'P_PMarzy', text='1')

            for key in ('P_PMarzy_2', 'P_PMarzy_3_1', 'P_PMarzy_3_2', 'P_PMarzy_3_3'):
                if invoice_data[key.lower()]:
                    self._x_ksef_create_element(margins_el, tns, key, text='1')
                    break

        else:
            self._x_ksef_create_element(margins_el, tns, 'P_PMarzyN', text='1')

    @api.model
    def _x_ksef_build_invoice_type(self, invoice_data, fa_el, tns):
        self._x_ksef_create_element(fa_el, tns, 'RodzajFaktury', text=invoice_data['invoice_type'])

    @api.model
    def _x_ksef_build_fp(self, invoice_data, fa_el, tns):
        if invoice_data['fp']:
            self._x_ksef_create_element(fa_el, tns, 'FP', text='1')

    @api.model
    def _x_ksef_build_tp(self, invoice_data, fa_el, tns):
        if invoice_data['tp']:
            self._x_ksef_create_element(fa_el, tns, 'TP', text='1')

    @api.model
    def _x_ksef_build_correction(self, invoice_data, fa_el, tns):
        if not invoice_data['invoice_type'].startswith('KOR') or not invoice_data['corrected_invoice']:
            return

        self._x_ksef_create_element(fa_el, tns, 'PrzyczynaKorekty', text=invoice_data['corrected_invoice']['reason'])

        self._x_ksef_create_element(fa_el, tns, 'TypKorekty', text='2')

        corrected_fa_el = self._x_ksef_create_element(fa_el, tns, 'DaneFaKorygowanej')
        self._x_ksef_create_element(
            corrected_fa_el, tns, 'DataWystFaKorygowanej', text=invoice_data['corrected_invoice']['invoice_date']
        )
        self._x_ksef_create_element(
            corrected_fa_el, tns, 'NrFaKorygowanej', text=invoice_data['corrected_invoice']['name']
        )

        if invoice_data['corrected_invoice']['ksef_number']:
            self._x_ksef_create_element(corrected_fa_el, tns, 'NrKSeF', text='1')
            self._x_ksef_create_element(
                corrected_fa_el, tns, 'NrKSeFFaKorygowanej', text=invoice_data['corrected_invoice']['ksef_number']
            )

        else:
            self._x_ksef_create_element(corrected_fa_el, tns, 'NrKSeFN', text='1')

    @api.model
    def _x_ksef_build_advance_invoice(self, invoice_data, fa_el, tns):
        for advance_invoice_data in invoice_data['advance_invoices']:
            advance_invoice_el = self._x_ksef_create_element(fa_el, tns, 'FakturaZaliczkowa')

            if advance_invoice_data['ksef_number']:
                self._x_ksef_create_element(
                    advance_invoice_el, tns, 'NrKSeFFaZaliczkowej', text=advance_invoice_data['ksef_number']
                )

            else:
                self._x_ksef_create_element(advance_invoice_el, tns, 'NrKSeFZN', text='1')
                self._x_ksef_create_element(
                    advance_invoice_el, tns, 'NrFaZaliczkowej', text=advance_invoice_data['name']
                )

    @api.model
    def _x_ksef_build_invoice_lines(self, invoice_data, fa_el, tns):
        if invoice_data['invoice_type'] == 'ZAL':
            return

        for line in invoice_data['lines']:
            line_el = self._x_ksef_create_element(fa_el, tns, 'FaWiersz')

            self._x_ksef_create_element(line_el, tns, 'NrWierszaFa', text=line['index'])

            if line['date'] is not None:
                self._x_ksef_create_element(line_el, tns, 'P_6A', text=line['date'])

            self._x_ksef_create_element(line_el, tns, 'P_7', text=line['name'])

            self._x_ksef_create_conditional_element(line_el, tns, 'GTIN', value=line['barcode'])

            self._x_ksef_create_conditional_element(line_el, tns, 'P_8A', value=line['uom_name'])
            self._x_ksef_create_element(line_el, tns, 'P_8B', text=line['quantity'])

            if invoice_data['price_include_tax']:
                self._x_ksef_create_element(line_el, tns, 'P_9B', text=line['price_unit'])

            else:
                self._x_ksef_create_element(line_el, tns, 'P_9A', text=line['price_unit_untaxed'])

            self._x_ksef_create_conditional_element(line_el, tns, 'P_10', value=line['discount'])

            if invoice_data['price_include_tax']:
                self._x_ksef_create_element(line_el, tns, 'P_11A', text=line['price_total'])

            else:
                self._x_ksef_create_element(line_el, tns, 'P_11', text=line['price_subtotal'])

            self._x_ksef_create_element(line_el, tns, 'P_12', text=line['tax_rate'])

            self._x_ksef_create_conditional_element(line_el, tns, 'GTU', value=line['gtu'])

            self._x_ksef_create_conditional_element(line_el, tns, 'KursWaluty', value=invoice_data['currency_rate'])
            self._x_ksef_create_conditional_element(line_el, tns, 'Procedura', value=line['procedure'])

            if invoice_data['invoice_type'].startswith('KOR') and not line['is_corrected']:
                self._x_ksef_create_element(line_el, tns, 'StanPrzed', text='1')

    @api.model
    def _x_ksef_build_payment(self, invoice_data, fa_el, tns):
        payment_el = self._x_ksef_create_element(fa_el, tns, 'Platnosc')

        if invoice_data['payments_data']['is_paid']:
            if len(invoice_data['payments_data']['payments']) == 1:
                self._x_ksef_create_element(payment_el, tns, 'Zaplacono', text='1')
                self._x_ksef_create_element(
                    payment_el, tns, 'DataZaplaty', text=invoice_data['payments_data']['payments'][0]['date']
                )

            elif len(invoice_data['payments_data']['payments']) > 1:
                self._x_ksef_create_element(payment_el, tns, 'ZnacznikZaplatyCzesciowej', text='2')

                for payment in invoice_data['payments_data']['payments']:
                    partial_payment_el = self._x_ksef_create_element(payment_el, tns, 'ZaplataCzesciowa')
                    self._x_ksef_create_element(
                        partial_payment_el, tns, 'KwotaZaplatyCzesciowej', text=payment['amount']
                    )
                    self._x_ksef_create_element(partial_payment_el, tns, 'DataZaplatyCzesciowej', text=payment['date'])

        elif invoice_data['payments_data']['is_partial']:
            self._x_ksef_create_element(payment_el, tns, 'ZnacznikZaplatyCzesciowej', text='1')

            for payment in invoice_data['payments_data']['payments']:
                partial_payment_el = self._x_ksef_create_element(payment_el, tns, 'ZaplataCzesciowa')
                self._x_ksef_create_element(partial_payment_el, tns, 'KwotaZaplatyCzesciowej', text=payment['amount'])
                self._x_ksef_create_element(partial_payment_el, tns, 'DataZaplatyCzesciowej', text=payment['date'])

        if invoice_data['invoice_date_due']:
            payment_term_el = self._x_ksef_create_element(payment_el, tns, 'TerminPlatnosci')
            self._x_ksef_create_element(payment_term_el, tns, 'Termin', text=invoice_data['invoice_date_due'])

        self._x_ksef_create_conditional_element(
            payment_el, tns, 'FormaPlatnosci', value=invoice_data['payment_term_type']
        )

        if invoice_data['partner_bank']:
            bank_account_el = self._x_ksef_create_element(payment_el, tns, 'RachunekBankowy')

            self._x_ksef_create_element(bank_account_el, tns, 'NrRB', text=invoice_data['partner_bank']['acc_number'])

            self._x_ksef_create_conditional_element(
                bank_account_el, tns, 'SWIFT', value=invoice_data['partner_bank']['bank_bic']
            )

            self._x_ksef_create_conditional_element(
                bank_account_el, tns, 'NazwaBanku', value=invoice_data['partner_bank']['bank_name']
            )

    @api.model
    def _x_ksef_build_transaction_conditions(self, invoice_data, fa_el, tns):
        if not (invoice_data['invoice_ref'] or invoice_data['orders_data']):
            return

        transaction_conditions_el = self._x_ksef_create_element(fa_el, tns, 'WarunkiTransakcji')

        invoice_ref_order_el = None
        if invoice_data['invoice_ref']:
            invoice_ref_order_el = self._x_ksef_create_element(transaction_conditions_el, tns, 'Zamowienia')
            self._x_ksef_create_element(invoice_ref_order_el, tns, 'NrZamowienia', text=invoice_data['invoice_ref'])

        for order_data in invoice_data['orders_data']:
            if invoice_ref_order_el and order_data['order_name'] == invoice_data['invoice_ref']:
                self._x_ksef_prepend_element(invoice_ref_order_el, tns, 'DataZamowienia', text=order_data['order_date'])
            else:
                order_el = self._x_ksef_create_element(transaction_conditions_el, tns, 'Zamowienia')
                self._x_ksef_create_element(order_el, tns, 'DataZamowienia', text=order_data['order_date'])
                self._x_ksef_create_element(order_el, tns, 'NrZamowienia', text=order_data['order_name'])

    @api.model
    def _x_ksef_build_order(self, invoice_data, fa_el, tns):
        if invoice_data['invoice_type'] != 'ZAL':
            return

        order_el = self._x_ksef_create_element(fa_el, tns, 'Zamowienie')

        self._x_ksef_create_element(order_el, tns, 'WartoscZamowienia', text=invoice_data['order_amount_total'])

        for order_line in invoice_data['order_lines']:
            order_line_el = self._x_ksef_create_element(order_el, tns, 'ZamowienieWiersz')

            self._x_ksef_create_element(order_line_el, tns, 'NrWierszaZam', text=order_line['index'])
            self._x_ksef_create_element(order_line_el, tns, 'P_7Z', text=order_line['name'])

            self._x_ksef_create_conditional_element(order_line_el, tns, 'GTINZ', value=order_line['barcode'])

            self._x_ksef_create_conditional_element(order_line_el, tns, 'P_8AZ', value=order_line['uom_name'])
            self._x_ksef_create_element(order_line_el, tns, 'P_8BZ', text=order_line['quantity'])
            self._x_ksef_create_element(order_line_el, tns, 'P_9AZ', text=order_line['price_unit_untaxed'])

            self._x_ksef_create_element(order_line_el, tns, 'P_11NettoZ', text=order_line['price_subtotal'])
            self._x_ksef_create_element(order_line_el, tns, 'P_11VatZ', text=order_line['price_tax'])
            self._x_ksef_create_element(order_line_el, tns, 'P_12Z', text=order_line['tax_rate'])

    @api.model
    def _x_ksef_build_footer(self, invoice_data, invoice_el, tns):
        footer_el = self._x_ksef_create_element(invoice_el, tns, 'Stopka')
        info_el = self._x_ksef_create_element(footer_el, tns, 'Informacje')

        self._x_ksef_create_conditional_element(info_el, tns, 'StopkaFaktury', value=invoice_data['invoice_narration'])

    @api.model
    def _x_ksef_get_invoice_xml(self, invoice_data):
        xsi = NS['xsi']
        tns = NS['tns']
        schema_location = 'StrukturyDanych_v10-0E.xsd'

        invoice_el = etree.Element(
            etree.QName(tns, 'Faktura'),
            attrib={etree.QName(xsi, 'schemaLocation'): schema_location},
            nsmap=NS,
        )

        self._x_ksef_build_header(invoice_el, tns)

        self._x_ksef_build_seller(invoice_data, invoice_el, tns)

        self._x_ksef_build_buyer(invoice_data, invoice_el, tns)

        fa_el = self._x_ksef_create_element(invoice_el, tns, 'Fa')

        self._x_ksef_build_fa_core(invoice_data, fa_el, tns)

        self._x_ksef_build_annotations(invoice_data, fa_el, tns)

        self._x_ksef_build_invoice_type(invoice_data, fa_el, tns)

        self._x_ksef_build_correction(invoice_data, fa_el, tns)

        self._x_ksef_build_fp(invoice_data, fa_el, tns)
        self._x_ksef_build_tp(invoice_data, fa_el, tns)

        self._x_ksef_build_advance_invoice(invoice_data, fa_el, tns)

        self._x_ksef_build_invoice_lines(invoice_data, fa_el, tns)

        self._x_ksef_build_payment(invoice_data, fa_el, tns)

        self._x_ksef_build_transaction_conditions(invoice_data, fa_el, tns)

        self._x_ksef_build_order(invoice_data, fa_el, tns)

        self._x_ksef_build_footer(invoice_data, invoice_el, tns)

        return etree.tostring(invoice_el, encoding='UTF-8', xml_declaration=True)

    # ========================================
    # IMPORT
    # ========================================

    @api.model
    def _x_ksef_get_invoice_batch_import_eligible_company_ids(self):
        return self.env['res.company'].search(
            [
                ('x_ksef_settings_id', '!=', False),
                ('x_ksef_purchase_journal_id', '!=', False),
            ]
        )

    @api.model
    def _x_ksef_get_invoice_batch_import_queue_key(self, company_id):
        return f'ksef_invoice_batch_import_queue_{company_id.id}'

    @api.model
    def _x_ksef_get_invoice_batch_import_state_key(self, company_id, batch_ref):
        return f'ksef_invoice_batch_import_state_{company_id.id}_{batch_ref}'

    @api.model
    def _x_ksef_start_invoice_batch_import(self, company_ids, date_from=None, date_to=None):
        default_date_from = fields.Datetime.subtract(fields.Datetime.now(), days=1)

        icp_id = self.env['ir.config_parameter'].sudo()

        for company_id in company_ids:
            client = company_id.x_ksef_get_authenticated_client()

            try:
                batch_ref = client.start_invoice_batch_export(
                    date_from=(date_from or company_id.x_ksef_purchase_invoice_sync_date or default_date_from),
                    date_to=date_to,
                )
            except KsefClientError as error:
                _logger.exception('KSeF batch import error for company %s: %s', company_id.id, str(error))
                continue

            _logger.info(
                'KSeF cron started batch import for company %s with batch reference %s.',
                company_id.id,
                batch_ref,
            )

            queue_key = self._x_ksef_get_invoice_batch_import_queue_key(company_id)

            current_queue = icp_id.get_param(queue_key)

            if not current_queue:
                current_queue = [batch_ref]
            else:
                current_queue = json.loads(current_queue)
                current_queue.append(batch_ref)

            icp_id.set_param(queue_key, json.dumps(current_queue))

            icp_id.set_param(
                self._x_ksef_get_invoice_batch_import_state_key(company_id, batch_ref),
                json.dumps(client.dump_invoice_batch_export_state()),
            )

    @api.model
    def _x_ksef_cron_start_invoice_batch_import(self):
        company_ids = self._x_ksef_get_invoice_batch_import_eligible_company_ids()

        self._x_ksef_start_invoice_batch_import(company_ids=company_ids)
        _logger.info('KSeF cron started invoice batch import for companies %s.', company_ids)

        self.env.ref('trilab_ksef.cron_check_invoice_batch_import_status')._trigger(
            at=fields.Datetime.add(fields.Datetime.now(), minutes=1)
        )

    def _x_ksef_check_invoice_batch_import_status(self, company_ids):
        icp_id = self.env['ir.config_parameter'].sudo()

        report_id = self.env.ref('trilab_ksef.action_report_invoice').sudo()

        for company_id in company_ids:
            queue_key = self._x_ksef_get_invoice_batch_import_queue_key(company_id)
            report_id = report_id.with_company(company=company_id)

            if not (current_queue := icp_id.get_param(queue_key)):
                continue

            client = company_id.x_ksef_get_authenticated_client()

            in_progress_batch_refs = []

            for batch_ref in json.loads(current_queue):
                state_key = self._x_ksef_get_invoice_batch_import_state_key(company_id, batch_ref)
                state_data = icp_id.get_param(state_key)

                if not state_data:
                    _logger.warning(
                        'KSeF batch %s import state not found for company %s, skipping...', batch_ref, company_id.id
                    )
                    continue

                client.load_invoice_batch_export_state(json.loads(state_data))

                try:
                    export_result = client.download_invoice_batch_export()

                except InvoiceBatchExportPendingError:
                    in_progress_batch_refs.append(batch_ref)
                    _logger.info(
                        'KSeF batch %s import still pending for company %s, will check again later...',
                        batch_ref,
                        company_id.id,
                    )
                    continue
                except KsefClientError as error:
                    _logger.exception(
                        'KSeF batch %s import error for company %s: %s', batch_ref, company_id.id, str(error)
                    )
                    icp_id.set_param(state_key, None)
                    continue

                if export_result is None:
                    icp_id.set_param(state_key, None)
                    continue

                try:
                    for filename, invoice_xml in export_result.invoices:
                        if (
                            self.env['ir.attachment'].search_count(
                                [
                                    ('name', '=', filename),
                                    ('res_model', '=', 'account.move'),
                                    ('res_field', '=', 'x_ksef_attachment_file'),
                                ],
                            )
                            > 0
                        ):
                            _logger.debug('Vendor bill already exists: %s', filename)
                            continue

                        try:
                            move_type = self.env['account.move']._x_ksef_get_vendor_move_type(
                                etree.fromstring(invoice_xml.encode())
                            )

                        except etree.ParseError:
                            move_type = 'in_invoice'

                        move_id = (
                            self.env['account.move']
                            .sudo()
                            .with_company(company_id)
                            .with_context(default_move_type=move_type)
                            .create({
                                'x_pl_ksef_invoice_number': filename[:-4] if filename.endswith('.xml') else filename,
                                'x_pl_ksef_invoice_proof': False,
                            })
                        )
                        attachment_id = (
                            self.sudo()
                            .env['ir.attachment']
                            .create(
                                {
                                    'name': filename,
                                    'raw': invoice_xml,
                                    'type': 'binary',
                                    'res_model': 'account.move',
                                    'res_id': move_id.id,
                                    'res_field': 'x_ksef_attachment_file',
                                }
                            )
                        )
                        move_id.invalidate_cache(fnames=['x_ksef_attachment_id', 'x_ksef_attachment_file'])
                        move_id.with_context(
                            account_predictive_bills_disable_prediction=True,
                            no_new_invoice=True,
                        ).message_post(
                            body=_(
                                'Invoice imported from KSeF during batch import (batch reference: %s), file: %s',
                                batch_ref,
                                filename,
                            ),
                            attachment_ids=attachment_id.ids,
                        )

                        self.with_company(company_id).with_context(
                            account_predictive_bills_disable_prediction=True
                        )._update_invoice_from_attachment(move_id.x_ksef_attachment_id, move_id)
                        move_id._x_ksef_create_report_attachment(report_id)
                        _logger.debug('Created %s from %s', move_id.name, filename)

                except KsefInvoiceBatchExportError:
                    _logger.exception(
                        'KSeF batch %s import error for company %s',
                        batch_ref,
                        company_id.id,
                    )
                    continue
                finally:
                    icp_id.set_param(state_key, None)

                company_id.x_ksef_purchase_invoice_sync_date = max(
                    company_id.x_ksef_purchase_invoice_sync_date or datetime.min,
                    export_result.permanent_storage_hwm_date.astimezone(timezone.utc).replace(tzinfo=None),
                )

                if export_result.is_truncated:
                    _logger.info('Batch import truncated scheduling next batch import in one minute')
                    self.env.ref('trilab_ksef.cron_start_invoice_batch_import')._trigger(
                        at=fields.Datetime.add(fields.Datetime.now(), minutes=1)
                    )

                self.env.cr.commit()

            if in_progress_batch_refs:
                _logger.debug(
                    'Some batch import still in progress, restoring queue and scheduling next check in one minute'
                )
                icp_id.set_param(queue_key, json.dumps(in_progress_batch_refs))
                self.env.ref('trilab_ksef.cron_check_invoice_batch_import_status')._trigger(
                    at=fields.Datetime.add(fields.Datetime.now(), minutes=1)
                )

            else:
                icp_id.set_param(queue_key, None)

    def _x_ksef_cron_check_invoice_batch_import_status(self):
        company_ids = self._x_ksef_get_invoice_batch_import_eligible_company_ids()

        self.env.ref('trilab_ksef.edi_ksef')._x_ksef_check_invoice_batch_import_status(company_ids=company_ids)
        _logger.info('KSeF cron checked invoice batch import status for companies %s.', company_ids)

    # noinspection PyMethodMayBeStatic
    def _x_ksef_is_vendor_bill_xml(self, file_xml_tree):
        if (form_code := next(iter(file_xml_tree.xpath('.//tns:KodFormularza', namespaces=NS)), None)) is not None:
            return form_code.attrib.get('kodSystemowy') == 'FA (3)' and form_code.attrib.get('wersjaSchemy') == '1-0E'
        return False

    def _update_invoice_from_xml_tree(self, filename, tree, invoice):
        self.ensure_one()

        if self._x_ksef_is_vendor_bill_xml(tree):
            return invoice._x_ksef_import_vendor_invoice(tree)

        return super()._update_invoice_from_xml_tree(filename, tree, invoice)
