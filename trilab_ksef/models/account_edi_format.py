import logging
import math
from datetime import date, datetime

import pytz
from lxml import etree
from lxml.builder import ElementMaker

from odoo import _, api, fields, models, tools
from odoo.tools import float_compare, float_is_zero, float_repr

from .ksef_client import KsefClientError

PL_CODE = 'PL'

_logger = logging.getLogger(__name__)

KSEF_CODE = 'ksef'
RELEASE_INFO = 'Trilab KSeF - (trilab_ksef {version})'

KSEF_MAX_PRICE_PRECISION = 8
KSEF_MAX_QTY_PRECISION = 6

NS_XSI = 'http://www.w3.org/2001/XMLSchema-instance'
# noinspection HttpUrlsUsage
NS_TNS = 'http://crd.gov.pl/wzor/2025/06/25/13775/'
# noinspection HttpUrlsUsage
NS_ETD = 'http://crd.gov.pl/xml/schematy/dziedzinowe/mf/2022/01/05/eD/DefinicjeTypy/'

NSMAP = {
    'tns': NS_TNS,
    'etd': NS_ETD,
    'xsi': NS_XSI,
}

SCHEMA_LOCATION = 'StrukturyDanych_v10-0E.xsd'


def _serialize_bool(element, value):
    element.text = '1' if value else '2'


def _serialize_date(element, value):
    element.text = value.isoformat()


def _serialize_datetime(element, value):
    element.text = value.isoformat()


def _truncate(value, max_len):
    return value[:max_len].strip() if value else value


NS_TYPES = {
    bool: _serialize_bool,
    date: _serialize_date,
    datetime: _serialize_datetime,
}

Etns = ElementMaker(typemap=NS_TYPES, namespace=NS_TNS, nsmap=NSMAP)


class AccountEdiFormat(models.Model):
    _inherit = 'account.edi.format'

    def _is_compatible_with_journal(self, journal):
        self.ensure_one()

        if self.code != KSEF_CODE:
            return super()._is_compatible_with_journal(journal)

        return journal.country_code == PL_CODE and journal.type == 'sale'

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

    def _get_move_applicability(self, move):
        self.ensure_one()

        if self.code != KSEF_CODE or not move.x_ksef_is_candidate():
            return super()._get_move_applicability(move)

        if move.x_is_refund() and not move.reversed_entry_id:
            _logger.info('KSeF refund invoice %s will not be sent - missing reversed_entry_id', move.id)
            return super()._get_move_applicability(move)

        if self.env.context.get('x_ksef_skip_resend') and move.x_ksef_session_reference:
            _logger.debug('KSeF invoice already sent for move %s skipping...', move.id)
            return None

        return {
            'post': self.x_ksef_post_edi,
            'edi_content': self._x_ksef_content_edi,
            # Note: this batching key is an empty list to override invoice.id key
            'post_batching': lambda _invoice_id: [],
        }

    @api.model
    def _x_ksef_move_configuration(self, move_id):
        errors = []

        if not move_id.company_id.x_ksef_settings_id:
            errors.append(_('- KSeF settings not configured for company: %s', move_id.company_id.name))

        if not move_id.company_id.x_ksef_plain_token:
            errors.append(_('- KSeF Token not configured for company: %s', move_id.company_id.name))

        if not move_id.company_id.x_use_ti:
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
                    '- Margin procedure selected. Only one of these fields must be selected: '
                    'Travel agencies, Used goods, Works of art, Antiques and collectibles'
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
            for _adv_inv_id in (move_id.x_advance_invoices_ids - move_id)
        ):
            errors.append(_('- KSeF Invoice Number is missing for some advance invoices'))

        if (
            move_id.reversed_entry_id.x_ksef_invoice_reference
            and not move_id.reversed_entry_id.x_pl_ksef_invoice_number
        ):
            errors.append(_('- KSeF Invoice Number is missing for reversed entry'))

        if move_id.x_is_refund() and move_id.reversed_entry_id:
            if len(move_id.x_original_invoice_line_ids) != len(move_id.x_corrected_invoice_line_ids):
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
    def _x_ksef_find_edi_document_attachment(self, invoice_id):
        edi_doc_id = fields.first(
            invoice_id.edi_document_ids.filtered(lambda d_id: d_id.edi_format_id.code == KSEF_CODE)
        )
        return edi_doc_id.sudo().attachment_id if edi_doc_id else self.env['ir.attachment']

    @api.model
    def _x_ksef_get_existing_edi_attachment(self, invoice_id):
        attachment_id = self._x_ksef_find_edi_document_attachment(invoice_id)
        return attachment_id.sudo().raw if attachment_id else None

    @api.model
    def _x_ksef_post_batch_edi(self, invoice_ids):
        invoice_xml_contents = [
            (
                invoice_id.x_ksef_get_invoice_file_name(),
                self._x_ksef_get_existing_edi_attachment(invoice_id) or self._x_ksef_content_edi(invoice_id),
            )
            for invoice_id in invoice_ids
        ]

        try:
            client = invoice_ids.company_id.x_ksef_get_authenticated_client()

            session_reference = client.start_invoice_batch_import(
                invoices=invoice_xml_contents,
            )
            client.close_invoice_batch_import()

        except KsefClientError as error:
            invoice_ids.company_id.x_ksef_notify_admins(
                note=invoice_ids.x_ksef_format_error_html(
                    error_title=_('KSeF batch invoice sending error'),
                    error=error,
                ),
            )
            return {
                invoice_id: {
                    'error': str(error),
                    'blocking_level': 'error',
                }
                for invoice_id in invoice_ids
            }

        _logger.info(f'KSeF batch EDI: sent {len(invoice_ids)} invoices in session {session_reference}')

        invoice_ids.update(
            {
                'x_ksef_last_invoice_status': None,
                'x_ksef_session_reference': session_reference,
                'x_ksef_session_type': 'batch',
            }
        )

        result = {}
        for invoice_id, (file_name, file_content) in zip(invoice_ids, invoice_xml_contents, strict=False):
            _logger.info(f'KSeF batch EDI: sent #{invoice_id.id} | {invoice_id.name} | {session_reference=}')
            existing_attachment_id = self._x_ksef_find_edi_document_attachment(invoice_id)
            result[invoice_id] = {
                'success': True,
                'attachment': existing_attachment_id
                or self.env['ir.attachment'].create(
                    {
                        'name': file_name,
                        'raw': file_content,
                        'res_model': 'account.move',
                        'res_id': invoice_id.id,
                        'mimetype': 'application/xml',
                    }
                ),
            }
        return result

    @api.model
    def _x_ksef_post_interactive_edi(self, invoice_id):
        attachment_id = self._x_ksef_find_edi_document_attachment(invoice_id)
        invoice_xml_content = attachment_id.sudo().raw if attachment_id else self._x_ksef_content_edi(invoice_id)

        try:
            client = invoice_id.company_id.x_ksef_get_authenticated_client()
            session_reference, _session_valid_until = client.open_interactive_session()
            ksef_invoice_reference = client.send_invoice(invoice_xml_content)
            client.close_interactive_session()

        except KsefClientError as error:
            invoice_id.company_id.x_ksef_notify_admins(
                note=invoice_id.x_ksef_format_error_html(
                    error_title=_('KSeF interactive invoice sending error'),
                    error=error,
                ),
            )
            return {
                invoice_id: {
                    'error': str(error),
                    'blocking_level': 'error',
                }
            }

        _logger.info(
            f'KSeF interactive EDI: sent invoice #{invoice_id.id} | {invoice_id.name} | {session_reference=} | {ksef_invoice_reference=}'
        )

        invoice_id.update(
            {
                'x_ksef_last_invoice_status': None,
                'x_ksef_invoice_reference': ksef_invoice_reference,
                'x_ksef_session_reference': session_reference,
                'x_ksef_session_type': 'interactive',
            }
        )

        if attachment_id:
            attachment_id.sudo().name = f'{ksef_invoice_reference}.xml'
        else:
            attachment_id = (
                self.env['ir.attachment']
                .with_context(tools.clean_context(self.env.context))
                .create(
                    {
                        'name': f'{ksef_invoice_reference}.xml',
                        'raw': invoice_xml_content,
                        'res_model': 'account.move',
                        'res_id': invoice_id.id,
                        'mimetype': 'application/xml',
                    }
                )
            )

        return {
            invoice_id: {
                'success': True,
                'attachment': attachment_id,
            }
        }

    def _x_ksef_content_edi(self, invoice_id):
        return self._x_ksef_get_invoice_xml(invoice_data=self._x_ksef_get_invoice_data(invoice_id))

    @api.model
    def _x_ksef_get_invoice_type(self, invoice_id):
        if invoice_id.move_type == 'out_invoice':
            if invoice_id._is_downpayment():
                return 'ZAL'

            if invoice_id.x_advance_invoices_ids:
                return 'ROZ'

            return 'VAT'

        if invoice_id.move_type == 'out_refund':
            if invoice_id._is_downpayment():
                return 'KOR_ZAL'

            if invoice_id.x_advance_invoices_ids:
                return 'KOR_ROZ'

            return 'KOR'

        return None

    @api.model
    def _x_ksef_get_header(self):
        return {
            'kod_formularza': 'FA',
            'kod_systemowy': 'FA (3)',
            'wersja_schemy': '1-0E',
            'wariant_formularza': '3',
            'data_wytworzenia': datetime.now(tz=pytz.UTC).isoformat(),
            'system_info': RELEASE_INFO.format(version=self.env['ir.module.module']._get('trilab_ksef').latest_version),
        }

    @api.model
    def _x_ksef_get_seller(self, invoice_id):
        seller_data = {
            'nip': invoice_id.company_id.partner_id.x_get_pl_vat(validate=False, raise_exception=False),
            'name': _truncate(invoice_id.company_id.name, 512),
            'address': {
                'country_code': invoice_id.company_id.country_id.code or PL_CODE,
                'address_line_1': _truncate(
                    ' '.join([invoice_id.company_id.street, invoice_id.company_id.zip, invoice_id.company_id.city]),
                    512,
                ),
                'address_line_2': _truncate(invoice_id.company_id.street2, 512) or None,
                'gln': None,
            },
            'phone': None,
            'email': None,
            'eori': None,
        }

        if invoice_id.company_id.x_ksef_enable_seller_contact_info:
            if phone := (invoice_id.company_id.phone or invoice_id.company_id.mobile):
                seller_data['phone'] = phone

            if email := (invoice_id.company_id.email or invoice_id.partner_id.email):
                seller_data['email'] = _truncate(email, 255)

        if invoice_id.company_id.partner_id.x_ksef_gln:
            seller_data['address']['gln'] = _truncate(invoice_id.company_id.x_ksef_gln, 13)

        if invoice_id.company_id.partner_id.x_ksef_eori:
            seller_data['eori'] = _truncate(invoice_id.company_id.partner_id.x_ksef_eori, 256)

        return seller_data

    @api.model
    def _x_ksef_get_buyer(self, invoice_id):
        buyer_data = {
            'name': _truncate(
                invoice_id.partner_id.commercial_company_name
                or invoice_id.partner_id.parent_id.name
                or invoice_id.partner_id.display_name,
                512,
            ),
            'address': {
                'country_code': invoice_id.partner_id.country_id.code or PL_CODE,
                'address_line_1': _truncate(
                    ' '.join(
                        filter(
                            None, (invoice_id.partner_id.street, invoice_id.partner_id.zip, invoice_id.partner_id.city)
                        )
                    ),
                    512,
                ),
                'address_line_2': _truncate(invoice_id.partner_id.street2, 512) or None,
                'gln': None,
            },
            'nip': invoice_id.partner_id.x_get_pl_vat(validate=False, raise_exception=False),
            'vat_eu': (vat_eu := invoice_id.partner_id.x_get_eu_vat()) and vat_eu[2:],
            'vat_eu_code': invoice_id.partner_id.x_get_eu_vat_country(),
            'tin': not vat_eu and (invoice_id.partner_id.vat or invoice_id.partner_id.company_registry),
            'phone': None,
            'email': None,
            'eori': None,
        }

        if invoice_id.company_id.x_ksef_enable_buyer_contact_info:
            if phone := (invoice_id.partner_id.phone or invoice_id.partner_id.mobile):
                buyer_data['phone'] = phone

            if email := invoice_id.partner_id.email:
                buyer_data['email'] = _truncate(email, 255)

        if invoice_id.partner_id.x_ksef_gln:
            buyer_data['address']['gln'] = _truncate(invoice_id.partner_id.x_ksef_gln, 13)

        if invoice_id.partner_id.x_ksef_eori:
            buyer_data['eori'] = _truncate(invoice_id.partner_id.x_ksef_eori, 256)

        return buyer_data

    @api.model
    def _x_ksef_get_third_parties(self, invoice_id):
        def _build_third_party(partner_id, role, role_other):
            return {
                'name': _truncate(
                    value=partner_id.commercial_company_name or partner_id.parent_id.name or partner_id.display_name,
                    max_len=512,
                ),
                'address': (
                    {
                        'address_line_1': _truncate(
                            value=' '.join(
                                filter(
                                    None,
                                    (
                                        partner_id.street,
                                        partner_id.zip,
                                        partner_id.city,
                                    ),
                                )
                            ),
                            max_len=512,
                        ),
                        'address_line_2': _truncate(partner_id.street2, 512) or None,
                        'gln': _truncate(partner_id.x_ksef_gln, 13) if partner_id.x_ksef_gln else None,
                    }
                    if partner_id.street
                    else None
                ),
                'nip': partner_id.x_get_pl_vat(validate=False, raise_exception=False),
                'vat_eu': (vat_eu := partner_id.x_get_eu_vat()) and vat_eu[2:],
                'vat_eu_code': partner_id.x_get_eu_vat_country(),
                'tin': not vat_eu and (partner_id.vat or partner_id.company_registry),
                'country_code': partner_id.country_id.code or PL_CODE,
                'role': role,
                'role_other': _truncate(role_other, 256),
                'internal_id': partner_id.x_ksef_internal_id,
            }

        third_parties = [
            _build_third_party(
                third_party_id.partner_id,
                role=third_party_id.classification,
                role_other=third_party_id.classification_other,
            )
            for third_party_id in invoice_id.x_ksef_third_party_ids
        ]

        if invoice_id.partner_shipping_id and invoice_id.partner_id != invoice_id.partner_shipping_id:
            shipping_id = invoice_id.partner_shipping_id

            if not (
                invoice_id.company_id.x_ksef_disable_shipping_third_party
                or shipping_id.x_ksef_disable_shipping_third_party
                or shipping_id.parent_id.x_ksef_disable_shipping_third_party
            ):
                third_parties.append(
                    _build_third_party(
                        shipping_id,
                        role='2',
                        role_other=None,
                    )
                )

        return third_parties

    @api.model
    def _x_ksef_get_outgoing_stock_pickings(self, invoice_id):
        if (
            not invoice_id.company_id.x_ksef_enable_outgoing_stock_pickings
            or self.env['ir.module.module']._get('sale_stock').state != 'installed'
        ):
            return None

        invoice_line_ids = invoice_id.invoice_line_ids.filtered('product_id')

        aml_key_set = {(aml.product_id.id, aml.quantity) for aml in invoice_line_ids}

        # noinspection PyUnresolvedReferences
        stock_move_ids = self.env['stock.move'].search(
            [
                ('sale_line_id', 'in', invoice_line_ids.sale_line_ids.ids),
                ('picking_type_id.code', '=', 'outgoing'),
            ]
        )

        # noinspection PyUnresolvedReferences
        return stock_move_ids.filtered(
            lambda sm_id: (sm_id.product_id.id, sm_id.quantity) in aml_key_set
        ).picking_id.mapped('name')

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
    def _x_ksef_amount_repr(self, value, *, precision_digits=2):
        result = float_repr(value=value, precision_digits=precision_digits)
        if '.' in result:
            result = result.rstrip('0').rstrip('.')
        return result

    @api.model
    def _x_ksef_get_invoice_lines(self, invoice_id):
        res = []

        price_precision = min(self.env['decimal.precision'].precision_get('Product Price'), KSEF_MAX_PRICE_PRECISION)
        qty_precision = min(
            self.env['decimal.precision'].precision_get('Product Unit of Measure'), KSEF_MAX_QTY_PRECISION
        )

        enable_barcodes = invoice_id.company_id.x_ksef_enable_barcodes

        invoice_line_ids = invoice_id.x_ksef_get_invoice_line_ids()

        for index, line_id in enumerate(invoice_line_ids, start=1):
            is_corrected_line = line_id.x_is_corrected_line
            quantity = line_id.quantity if not is_corrected_line else line_id.x_quantity

            taxes_res = line_id.tax_ids.compute_all(
                line_id.price_unit,
                quantity=math.copysign(1.0, quantity),
                currency=line_id.currency_id,
                product=line_id.product_id,
                partner=line_id.partner_id,
                is_refund=line_id.is_refund,
            )
            price_unit_untaxed = taxes_res['total_excluded']
            price_unit = taxes_res['total_included']

            if invoice_id.x_ksef_invoice_date_applicability == 'itemized':
                # field in account_accountant - enterprise version
                line_date = getattr(line_id, 'deferred_end_date', None) or line_id.move_id.x_invoice_sale_date

            else:
                line_date = None

            discount_amount = None
            discount_amount_untaxed = None

            if not float_is_zero(
                line_id.discount, precision_digits=self.env['decimal.precision'].precision_get('Discount')
            ):
                discount_taxes_res = line_id.tax_ids.compute_all(
                    line_id.price_unit * (line_id.discount / 100),
                    quantity=1,
                    currency=line_id.currency_id,
                    product=line_id.product_id,
                    partner=line_id.partner_id,
                    is_refund=line_id.is_refund,
                )

                discount_amount = self._x_ksef_amount_repr(
                    discount_taxes_res['total_included'],
                    precision_digits=price_precision,
                )
                discount_amount_untaxed = self._x_ksef_amount_repr(
                    discount_taxes_res['total_excluded'],
                    precision_digits=price_precision,
                )

            res.append(
                {
                    'line_id': line_id,
                    'index': str(index),
                    'uom_name': _truncate(
                        value=(
                            line_id.product_uom_id.with_context(lang=invoice_id.partner_id.lang).name
                            if line_id.product_uom_id
                            else None
                        ),
                        max_len=256,
                    ),
                    'name': _truncate(line_id.name, 512),
                    'quantity': self._x_ksef_amount_repr(
                        quantity,
                        precision_digits=qty_precision,
                    ),
                    'price_subtotal': self._x_ksef_amount_repr(
                        line_id.price_subtotal if not is_corrected_line else line_id.x_price_subtotal
                    ),
                    'price_total': self._x_ksef_amount_repr(
                        line_id.price_total if not is_corrected_line else line_id.x_price_total
                    ),
                    'price_unit_untaxed': self._x_ksef_amount_repr(
                        price_unit_untaxed,
                        precision_digits=price_precision,
                    ),
                    'price_unit': self._x_ksef_amount_repr(
                        price_unit,
                        precision_digits=price_precision,
                    ),
                    'discount_amt': discount_amount,
                    'discount_amt_untaxed': discount_amount_untaxed,
                    'tax_rate': fields.first(line_id.tax_ids).x_ksef_amount,
                    'barcode': _truncate(
                        value=line_id.product_id.barcode if enable_barcodes else None,
                        max_len=20,
                    ),
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

        price_precision = min(
            self.env['decimal.precision'].precision_get('Product Price'),
            KSEF_MAX_PRICE_PRECISION,
        )

        qty_precision = min(
            self.env['decimal.precision'].precision_get('Product Unit of Measure'),
            KSEF_MAX_QTY_PRECISION,
        )

        enable_barcodes = invoice_id.company_id.x_ksef_enable_barcodes

        order_line_ids = invoice_id.line_ids.sale_line_ids.order_id.order_line.filtered(
            lambda _l_id: not _l_id.display_type and not _l_id.is_downpayment
        )

        if invoice_id.company_id.x_ksef_enable_ignore_zero_amount_lines:
            order_line_ids = order_line_ids.filtered(lambda _l_id: not float_is_zero(_l_id.price_unit, price_precision))

        for index, line_id in enumerate(order_line_ids, start=1):
            res.append(
                {
                    'index': str(index),
                    'uom_name': _truncate(
                        value=(
                            line_id.product_uom.with_context(lang=invoice_id.partner_id.lang).name
                            if line_id.product_uom
                            else None
                        ),
                        max_len=256,
                    ),
                    'name': _truncate(line_id.name, 512),
                    'quantity': self._x_ksef_amount_repr(
                        line_id.product_uom_qty,
                        precision_digits=qty_precision,
                    ),
                    'price_subtotal': self._x_ksef_amount_repr(line_id.price_subtotal),
                    'price_unit_untaxed': self._x_ksef_amount_repr(
                        (
                            line_id.currency_id.round(line_id.price_subtotal / line_id.product_uom_qty)
                            if line_id.product_uom_qty
                            else 0.0
                        ),
                        precision_digits=price_precision,
                    ),
                    'price_tax': self._x_ksef_amount_repr(line_id.price_tax),
                    'tax_rate': fields.first(line_id.tax_id).x_ksef_amount,
                    'barcode': _truncate(
                        value=line_id.product_id.barcode if enable_barcodes else None,
                        max_len=20,
                    ),
                }
            )

        return res

    @api.model
    def _x_ksef_get_orders_data(self, invoice_id):
        return [
            {
                'order_date': _order_id.date_order.date(),
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
                'payments': [{'date': invoice_id.invoice_date}],
            }

        elif invoice_id.invoice_payment_term_id.x_ksef_payment_state_mapping == 'not_paid':
            return {
                'is_paid': False,
                'is_partial': False,
                'payments': [],
            }

        payments_content = invoice_id.invoice_payments_widget and invoice_id.invoice_payments_widget['content'] or []

        return {
            'is_paid': invoice_id.payment_state == 'paid',
            'is_partial': invoice_id.payment_state == 'partial',
            'payments': [
                {
                    'amount': self._x_ksef_amount_repr(val['amount']),
                    'date': val['date'],
                }
                for val in payments_content
                if not val.get('is_exchange')
            ],
        }

    @api.model
    def _x_ksef_get_invoice_currency_rate(self, invoice_id):
        if invoice_id.currency_id == invoice_id.company_currency_id:
            return None

        if not float_is_zero(invoice_id.x_invoice_currency_rate, precision_digits=4):
            return float_repr(invoice_id.x_invoice_currency_rate, precision_digits=4)

        return float_repr(
            abs(invoice_id.company_currency_id.round(invoice_id.amount_total_signed / invoice_id.amount_total)),
            precision_digits=4,
        )

    @api.model
    def _x_ksef_get_tax_totals(self, invoice_id):
        tax_totals = invoice_id.x_patched_tax_totals()

        if invoice_id.x_final_source_id or (invoice_id.reversed_entry_id and invoice_id.x_advance_source_id):
            tax_totals = invoice_id.x_get_final_invoice_summary(
                with_downpayments=invoice_id.x_final_source_id
                or (invoice_id.reversed_entry_id and invoice_id.x_advance_source_id)
            )

        return tax_totals

    @api.model
    def _x_ksef_get_tax_base_amount(self, invoice_id, tax_amounts, field='base_amount_currency'):
        tax_groups = invoice_id.invoice_line_ids.tax_ids.filtered(
            lambda t_id: any(
                float_compare(t_id.amount, tax_amount, precision_digits=2) == 0 for tax_amount in tax_amounts
            )
        ).tax_group_id.ids

        tax_totals = self._x_ksef_get_tax_totals(invoice_id)

        flat_tax_groups = [tax_group for subtotal in tax_totals['subtotals'] for tax_group in subtotal['tax_groups']]

        if not flat_tax_groups or not tax_groups:
            return None

        return self._x_ksef_amount_repr(
            sum(group[field] for group in flat_tax_groups if group['id'] in tax_groups),
        )

    @api.model
    def _x_ksef_get_tax_amount(self, invoice_id, tax_amounts, field='tax_amount_currency'):
        return self._x_ksef_get_tax_base_amount(invoice_id, tax_amounts, field=field)

    @api.model
    def _x_ksef_get_zero_tax_base_amount(self, invoice_id, ksef_tax_amount):
        filtered_line_ids = invoice_id.invoice_line_ids.filtered(
            lambda l_id: (tax_id := fields.first(l_id.tax_ids)) and tax_id.x_ksef_amount == ksef_tax_amount
        )

        if not filtered_line_ids:
            return None

        return self._x_ksef_amount_repr(-sum(filtered_line_ids.mapped('amount_currency')))

    @api.model
    def _x_ksef_get_invoice_data(self, invoice_id):
        third_parties = self._x_ksef_get_third_parties(invoice_id)

        return {
            'header': self._x_ksef_get_header(),
            'seller': self._x_ksef_get_seller(invoice_id),
            'buyer': self._x_ksef_get_buyer(invoice_id),
            'third_parties': third_parties,
            'buyer_jst': any(tp['role'] == '8' for tp in third_parties),
            'buyer_gv': any(tp['role'] == '10' for tp in third_parties),
            'outgoing_stock_pickings': self._x_ksef_get_outgoing_stock_pickings(invoice_id),
            'currency_code': invoice_id.currency_id.name,
            'p_1': invoice_id.invoice_date,
            'p_2': invoice_id.name,
            'p_6': invoice_id.x_invoice_sale_date,
            'p_13_1': self._x_ksef_get_tax_base_amount(invoice_id, (22, 23)),
            'p_14_1': self._x_ksef_get_tax_amount(invoice_id, (22, 23)),
            'p_14_1w': (
                self._x_ksef_get_tax_amount(invoice_id, (22, 23), field='tax_amount')
                if invoice_id.currency_id != invoice_id.company_currency_id
                else None
            ),
            'p_13_2': self._x_ksef_get_tax_base_amount(invoice_id, (7, 8)),
            'p_14_2': self._x_ksef_get_tax_amount(invoice_id, (7, 8)),
            'p_14_2w': (
                self._x_ksef_get_tax_amount(invoice_id, (7, 8), field='tax_amount')
                if invoice_id.currency_id != invoice_id.company_currency_id
                else None
            ),
            'p_13_3': self._x_ksef_get_tax_base_amount(invoice_id, (5,)),
            'p_14_3': self._x_ksef_get_tax_amount(invoice_id, (5,)),
            'p_14_3w': (
                self._x_ksef_get_tax_amount(invoice_id, (5,), field='tax_amount')
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
            'p_15': self._x_ksef_amount_repr(self._x_ksef_get_tax_totals(invoice_id)['total_amount_currency']),
            'currency_rate': self._x_ksef_get_invoice_currency_rate(invoice_id),
            'p_16': invoice_id.x_ksef_p_16,
            'p_17': invoice_id.x_ksef_p_17,
            'p_18': invoice_id.x_pl_vat_reverse_charge,
            'p_18a': invoice_id.x_pl_vat_mpp,
            'p_19': invoice_id.x_ksef_p_19,
            'p_19a': _truncate(invoice_id.x_ksef_p_19 and invoice_id.x_ksef_p_19a, 256),
            'p_19b': _truncate(invoice_id.x_ksef_p_19 and invoice_id.x_ksef_p_19b, 256),
            'p_19c': _truncate(invoice_id.x_ksef_p_19 and invoice_id.x_ksef_p_19c, 256),
            'p_22n': 1,
            'p_23': invoice_id.x_pl_vat_tt_d,
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
            'invoice_ref': _truncate(
                value=invoice_id.ref or invoice_id.invoice_origin,
                max_len=255,
            ),
            'price_include_tax': fields.first(invoice_id.invoice_line_ids.tax_ids).price_include,
            'invoice_id': invoice_id,
            'invoice_date_due': invoice_id.invoice_date_due,
            'payment_term_type': invoice_id.invoice_payment_term_id.x_ksef_payment_term_type,
            'partner_bank': (
                {
                    'acc_number': invoice_id.partner_bank_id.sanitized_acc_number,
                    'bank_bic': invoice_id.partner_bank_id.bank_bic,
                    'bank_name': _truncate(invoice_id.partner_bank_id.bank_name, 255),
                }
                if invoice_id.partner_bank_id
                else None
            ),
            'invoice_narration': _truncate(
                value=invoice_id.narration.striptags().strip() if invoice_id.narration else None,
                max_len=3500,
            ),
            'advance_invoices': [
                {
                    'name': _adv_inv_id.name,
                    'ksef_number': _adv_inv_id.x_pl_ksef_invoice_number,
                }
                for _adv_inv_id in invoice_id.x_advance_invoices_ids
            ],
            'corrected_invoice': (
                {
                    'name': invoice_id.reversed_entry_id.name,
                    'ksef_number': invoice_id.reversed_entry_id.x_pl_ksef_invoice_number,
                    'invoice_date': invoice_id.reversed_entry_id.invoice_date,
                    'reason': _truncate(invoice_id.ref, 256),
                }
                if invoice_id.reversed_entry_id
                else None
            ),
            'fp': invoice_id.x_pl_vat_typ_dokumentu == 'FP',
            'tp': invoice_id.x_pl_vat_tp,
            'payments_data': self._x_ksef_get_invoice_payments_data(invoice_id),
        }

    @api.model
    def _x_ksef_build_header(self, invoice_data):
        header = invoice_data['header']
        system_info = header.get('system_info')

        return Etns.Naglowek(
            Etns.KodFormularza(
                header['kod_formularza'], kodSystemowy=header['kod_systemowy'], wersjaSchemy=header['wersja_schemy']
            ),
            Etns.WariantFormularza(header['wariant_formularza']),
            Etns.DataWytworzeniaFa(header['data_wytworzenia']),
            *([Etns.SystemInfo(system_info)] if system_info else []),
        )

    @api.model
    def _x_ksef_build_seller(self, invoice_data):
        seller = invoice_data['seller']
        addr = seller['address']

        contact_info_elements = []

        if email := seller.get('email'):
            contact_info_elements.append(Etns.Email(email))

        if phone := seller.get('phone'):
            contact_info_elements.append(Etns.Telefon(phone))

        return Etns.Podmiot1(
            *([Etns.NrEORI(seller['eori'])] if seller['eori'] else []),
            Etns.DaneIdentyfikacyjne(
                Etns.NIP(seller['nip']),
                Etns.Nazwa(seller['name']),
            ),
            Etns.Adres(
                Etns.KodKraju(addr['country_code']),
                Etns.AdresL1(addr['address_line_1']),
                *([Etns.AdresL2(addr['address_line_2'])] if addr['address_line_2'] else []),
                *([Etns.GLN(addr['gln'])] if addr['gln'] else []),
            ),
            *([Etns.DaneKontaktowe(*contact_info_elements)] if contact_info_elements else []),
        )

    @api.model
    def _x_ksef_build_buyer(self, invoice_data):
        buyer = invoice_data['buyer']
        addr = buyer['address']

        id_elements = Etns.DaneIdentyfikacyjne()

        if buyer['nip']:
            id_elements.append(Etns.NIP(buyer['nip']))

        elif buyer['vat_eu']:
            id_elements.append(Etns.KodUE(buyer['vat_eu_code']))
            id_elements.append(Etns.NrVatUE(buyer['vat_eu']))

        elif buyer['tin']:
            id_elements.append(Etns.KodKraju(addr['country_code']))
            id_elements.append(Etns.NrID(buyer['tin']))

        else:
            id_elements.append(Etns.BrakID('1'))

        id_elements.append(Etns.Nazwa(buyer['name']))

        contact_info_elements = []

        if buyer.get('email'):
            contact_info_elements.append(Etns.Email(buyer['email']))

        if buyer.get('phone'):
            contact_info_elements.append(Etns.Telefon(buyer['phone']))

        return Etns.Podmiot2(
            *([Etns.NrEORI(buyer['eori'])] if buyer['eori'] else []),
            id_elements,
            Etns.Adres(
                Etns.KodKraju(addr['country_code']),
                Etns.AdresL1(addr['address_line_1']),
                *([Etns.AdresL2(addr['address_line_2'])] if addr['address_line_2'] else []),
                *([Etns.GLN(addr['gln'])] if addr['gln'] else []),
            ),
            *([Etns.DaneKontaktowe(*contact_info_elements)] if contact_info_elements else []),
            Etns.JST('1' if invoice_data['buyer_jst'] else '2'),
            Etns.GV('1' if invoice_data['buyer_gv'] else '2'),
        )

    @api.model
    def _x_ksef_build_third_parties(self, invoice_data):
        elements = []

        for third_party in invoice_data['third_parties']:
            id_elements = Etns.DaneIdentyfikacyjne()

            if third_party['nip']:
                id_elements.append(Etns.NIP(third_party['nip']))

            elif third_party['internal_id']:
                id_elements.append(Etns.IDWew(third_party['internal_id']))

            elif third_party['vat_eu']:
                id_elements.append(Etns.KodUE(third_party['vat_eu_code']))
                id_elements.append(Etns.NrVatUE(third_party['vat_eu']))

            elif third_party['tin']:
                id_elements.append(Etns.KodKraju(third_party['country_code']))
                id_elements.append(Etns.NrID(third_party['tin']))

            else:
                id_elements.append(Etns.BrakID('1'))

            id_elements.append(Etns.Nazwa(third_party['name']))

            if third_party['role'] == '-1':
                role_elements = [
                    Etns.RolaInna('1'),
                    Etns.OpisRoli(third_party['role_other']),
                ]
            else:
                role_elements = [Etns.Rola(third_party['role'])]

            elements.append(
                Etns.Podmiot3(
                    id_elements,
                    *(
                        [
                            Etns.Adres(
                                Etns.KodKraju(third_party['country_code']),
                                Etns.AdresL1(addr['address_line_1']),
                                *([Etns.AdresL2(addr['address_line_2'])] if addr['address_line_2'] else []),
                                *([Etns.GLN(addr['gln'])] if addr['gln'] else []),
                            )
                        ]
                        if (addr := third_party['address']) is not None
                        else []
                    ),
                    *role_elements,
                )
            )

        return elements

    @api.model
    def _x_ksef_build_fa_core(self, invoice_data):
        elements = [
            Etns.KodWaluty(invoice_data['currency_code']),
            Etns.P_1(invoice_data['p_1']),
            Etns.P_2(invoice_data['p_2']),
        ]

        if invoice_data['outgoing_stock_pickings']:
            for stock_picking in invoice_data['outgoing_stock_pickings']:
                elements.append(Etns.WZ(stock_picking))

        if all(_line['date'] is None for _line in invoice_data['lines']):
            elements.append(Etns.P_6(invoice_data['p_6']))

        for tax_i in range(1, 4):
            if (p_13_value := invoice_data[f'p_13_{tax_i}']) is not None:
                elements.append(getattr(Etns, f'P_13_{tax_i}')(p_13_value))

            if (p_14_value := invoice_data[f'p_14_{tax_i}']) is not None:
                elements.append(getattr(Etns, f'P_14_{tax_i}')(p_14_value))

            if (p_14_w := invoice_data[f'p_14_{tax_i}w']) is not None:
                elements.append(getattr(Etns, f'P_14_{tax_i}W')(p_14_w))

        for zero_tax in ('P_13_6_1', 'P_13_6_2', 'P_13_6_3', 'P_13_7', 'P_13_8', 'P_13_9', 'P_13_10'):
            if (zero_tax_value := invoice_data[zero_tax.lower()]) is not None:
                elements.append(getattr(Etns, zero_tax)(zero_tax_value))

        elements.append(Etns.P_15(invoice_data['p_15']))

        return elements

    @api.model
    def _x_ksef_build_annotations(self, invoice_data):
        exemption_children = []
        if invoice_data['p_19']:
            exemption_children.append(Etns.P_19('1'))
            for key in ('P_19A', 'P_19B', 'P_19C'):
                if invoice_data[key.lower()]:
                    exemption_children.append(getattr(Etns, key)(invoice_data[key.lower()]))
                    break
        else:
            exemption_children.append(Etns.P_19N('1'))

        margin_children = []
        if invoice_data['p_pmarzy']:
            margin_children.append(Etns.P_PMarzy('1'))
            for key in ('P_PMarzy_2', 'P_PMarzy_3_1', 'P_PMarzy_3_2', 'P_PMarzy_3_3'):
                if invoice_data[key.lower()]:
                    margin_children.append(getattr(Etns, key)('1'))
                    break
        else:
            margin_children.append(Etns.P_PMarzyN('1'))

        return Etns.Adnotacje(
            Etns.P_16(invoice_data['p_16']),
            Etns.P_17(invoice_data['p_17']),
            Etns.P_18(invoice_data['p_18']),
            Etns.P_18A(invoice_data['p_18a']),
            Etns.Zwolnienie(*exemption_children),
            Etns.NoweSrodkiTransportu(
                *([Etns.P_22N('1')] if invoice_data['p_22n'] else []),
            ),
            Etns.P_23(invoice_data['p_23']),
            Etns.PMarzy(*margin_children),
        )

    @api.model
    def _x_ksef_build_invoice_type(self, invoice_data):
        return Etns.RodzajFaktury(invoice_data['invoice_type'])

    @api.model
    def _x_ksef_build_fp(self, invoice_data):
        return Etns.FP('1') if invoice_data['fp'] else None

    @api.model
    def _x_ksef_build_tp(self, invoice_data):
        return Etns.TP('1') if invoice_data['tp'] else None

    @api.model
    def _x_ksef_build_correction(self, invoice_data):
        if not invoice_data['invoice_type'].startswith('KOR') or not invoice_data['corrected_invoice']:
            return []

        corrected = invoice_data['corrected_invoice']

        if corrected['ksef_number']:
            ksef_children = [
                Etns.NrKSeF('1'),
                Etns.NrKSeFFaKorygowanej(corrected['ksef_number']),
            ]
        else:
            ksef_children = [Etns.NrKSeFN('1')]

        return [
            Etns.PrzyczynaKorekty(corrected['reason']),
            Etns.TypKorekty('2'),
            Etns.DaneFaKorygowanej(
                Etns.DataWystFaKorygowanej(corrected['invoice_date']),
                Etns.NrFaKorygowanej(corrected['name']),
                *ksef_children,
            ),
        ]

    @api.model
    def _x_ksef_build_advance_invoice(self, invoice_data):
        elements = []
        for advance_invoice in invoice_data['advance_invoices']:
            if advance_invoice['ksef_number']:
                elements.append(
                    Etns.FakturaZaliczkowa(
                        Etns.NrKSeFFaZaliczkowej(advance_invoice['ksef_number']),
                    )
                )
            else:
                elements.append(
                    Etns.FakturaZaliczkowa(
                        Etns.NrKSeFZN('1'),
                        Etns.NrFaZaliczkowej(advance_invoice['name']),
                    )
                )
        return elements

    @api.model
    def _x_ksef_build_invoice_lines(self, invoice_data):
        if invoice_data['invoice_type'] == 'ZAL':
            return []

        is_kor = invoice_data['invoice_type'].startswith('KOR')
        price_include_tax = invoice_data['price_include_tax']
        elements = []

        for line in invoice_data['lines']:
            children = [Etns.NrWierszaFa(line['index'])]

            if line['date'] is not None:
                children.append(Etns.P_6A(line['date']))

            children.append(Etns.P_7(line['name']))

            if line['barcode']:
                children.append(Etns.GTIN(line['barcode']))

            if line['uom_name'] is not None:
                children.append(Etns.P_8A(line['uom_name']))

            children.append(Etns.P_8B(line['quantity']))

            if price_include_tax:
                children.append(Etns.P_9B(line['price_unit']))

                if line['discount_amt']:
                    children.append(Etns.P_10(line['discount_amt']))

            else:
                children.append(Etns.P_9A(line['price_unit_untaxed']))

                if line['discount_amt_untaxed']:
                    children.append(Etns.P_10(line['discount_amt_untaxed']))

            if price_include_tax:
                children.append(Etns.P_11A(line['price_total']))
            else:
                children.append(Etns.P_11(line['price_subtotal']))

            children.append(Etns.P_12(line['tax_rate']))

            if line['gtu']:
                children.append(Etns.GTU(line['gtu']))

            if line['procedure']:
                children.append(Etns.Procedura(line['procedure']))

            if invoice_data['currency_rate']:
                children.append(Etns.KursWaluty(invoice_data['currency_rate']))

            if is_kor and not line['is_corrected']:
                children.append(Etns.StanPrzed('1'))

            elements.append(Etns.FaWiersz(*children))

        return elements

    @api.model
    def _x_ksef_build_payment(self, invoice_data):
        children = []
        payments_data = invoice_data['payments_data']

        if payments_data['is_paid']:
            if len(payments_data['payments']) == 1:
                children.append(Etns.Zaplacono('1'))
                children.append(Etns.DataZaplaty(payments_data['payments'][0]['date']))

            elif len(payments_data['payments']) > 1:
                children.append(Etns.ZnacznikZaplatyCzesciowej('2'))
                for payment in payments_data['payments']:
                    children.append(
                        Etns.ZaplataCzesciowa(
                            Etns.KwotaZaplatyCzesciowej(payment['amount']),
                            Etns.DataZaplatyCzesciowej(payment['date']),
                        )
                    )

        elif payments_data['is_partial']:
            children.append(Etns.ZnacznikZaplatyCzesciowej('1'))
            for payment in payments_data['payments']:
                children.append(
                    Etns.ZaplataCzesciowa(
                        Etns.KwotaZaplatyCzesciowej(payment['amount']),
                        Etns.DataZaplatyCzesciowej(payment['date']),
                    )
                )

        if invoice_data['invoice_date_due']:
            children.append(
                Etns.TerminPlatnosci(
                    Etns.Termin(invoice_data['invoice_date_due']),
                )
            )

        if invoice_data['payment_term_type']:
            children.append(Etns.FormaPlatnosci(invoice_data['payment_term_type']))

        if invoice_data['partner_bank']:
            bank = invoice_data['partner_bank']
            bank_children = [Etns.NrRB(bank['acc_number'])]
            if bank['bank_bic']:
                bank_children.append(Etns.SWIFT(bank['bank_bic']))
            if bank['bank_name']:
                bank_children.append(Etns.NazwaBanku(bank['bank_name']))
            children.append(Etns.RachunekBankowy(*bank_children))

        return Etns.Platnosc(*children)

    @api.model
    def _x_ksef_build_transaction_conditions(self, invoice_data):
        if not (invoice_data['invoice_ref'] or invoice_data['orders_data']):
            return None

        order_elements = []
        invoice_ref = invoice_data['invoice_ref']
        invoice_ref_order_el = None

        if invoice_ref and (invoice_data.get('corrected_invoice') or {}).get('reason') != invoice_ref:
            invoice_ref_order_el = Etns.Zamowienia(Etns.NrZamowienia(invoice_ref))
            order_elements.append(invoice_ref_order_el)

        for order_data in invoice_data['orders_data']:
            if invoice_ref_order_el is not None and order_data['order_name'] == invoice_ref:
                invoice_ref_order_el.insert(0, Etns.DataZamowienia(order_data['order_date']))
            else:
                order_elements.append(
                    Etns.Zamowienia(
                        Etns.DataZamowienia(order_data['order_date']),
                        Etns.NrZamowienia(order_data['order_name']),
                    )
                )

        return Etns.WarunkiTransakcji(*order_elements)

    @api.model
    def _x_ksef_build_order(self, invoice_data):
        if invoice_data['invoice_type'] != 'ZAL':
            return None

        order_line_elements = []
        for ol in invoice_data['order_lines']:
            children = [
                Etns.NrWierszaZam(ol['index']),
                Etns.P_7Z(ol['name']),
            ]
            if ol['barcode']:
                children.append(Etns.GTINZ(ol['barcode']))

            if ol['uom_name'] is not None:
                children.append(Etns.P_8AZ(ol['uom_name']))

            children.extend(
                [
                    Etns.P_8BZ(ol['quantity']),
                    Etns.P_9AZ(ol['price_unit_untaxed']),
                    Etns.P_11NettoZ(ol['price_subtotal']),
                    Etns.P_11VatZ(ol['price_tax']),
                    Etns.P_12Z(ol['tax_rate']),
                ]
            )
            order_line_elements.append(Etns.ZamowienieWiersz(*children))

        return Etns.Zamowienie(
            Etns.WartoscZamowienia(invoice_data['order_amount_total']),
            *order_line_elements,
        )

    @api.model
    def _x_ksef_build_footer(self, invoice_data):
        return Etns.Stopka(
            Etns.Informacje(
                *([Etns.StopkaFaktury(invoice_data['invoice_narration'])] if invoice_data['invoice_narration'] else []),
            ),
        )

    @api.model
    def _x_ksef_get_invoice_xml(self, invoice_data):
        fa_children = [
            *self._x_ksef_build_fa_core(invoice_data),
            self._x_ksef_build_annotations(invoice_data),
            self._x_ksef_build_invoice_type(invoice_data),
            *self._x_ksef_build_correction(invoice_data),
            *([self._x_ksef_build_fp(invoice_data)] if invoice_data['fp'] else []),
            *([self._x_ksef_build_tp(invoice_data)] if invoice_data['tp'] else []),
            *self._x_ksef_build_advance_invoice(invoice_data),
            *self._x_ksef_build_invoice_lines(invoice_data),
            self._x_ksef_build_payment(invoice_data),
        ]

        transaction_conditions = self._x_ksef_build_transaction_conditions(invoice_data)
        if transaction_conditions is not None:
            fa_children.append(transaction_conditions)

        order = self._x_ksef_build_order(invoice_data)
        if order is not None:
            fa_children.append(order)

        faktura = Etns.Faktura(
            {etree.QName(NS_XSI, 'schemaLocation'): SCHEMA_LOCATION},
            self._x_ksef_build_header(invoice_data),
            self._x_ksef_build_seller(invoice_data),
            self._x_ksef_build_buyer(invoice_data),
            *self._x_ksef_build_third_parties(invoice_data),
            Etns.Fa(*fa_children),
            self._x_ksef_build_footer(invoice_data),
        )

        faktura = self._x_ksef_post_process_invoice_xml(faktura, invoice_data)

        return etree.tostring(faktura, encoding='UTF-8', xml_declaration=True)

    # noinspection PyUnusedLocal
    @api.model
    def _x_ksef_post_process_invoice_xml(self, faktura, invoice_data):
        # Note: to be overridden
        return faktura
