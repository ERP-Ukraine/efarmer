import base64
import json
import logging
from datetime import UTC, date, datetime

from lxml import etree
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_is_zero
from odoo.tools.image import image_data_uri
from odoo.tools.safe_eval import dateutil, safe_eval, time
from odoo.tools.xml_utils import find_xml_value

from .account_edi_format import KSEF_CODE, NSMAP
from .ksef_client import (
    InvoiceBatchExportPendingError,
    KsefClient,
    KsefClientError,
    KsefInvoiceBatchExportError,
    KsefStatusCode,
)
from .ksef_xml_utils import parse_ksef_xml

_logger = logging.getLogger(__name__)

VENDOR_MOVE_TYPE_MAPPING = {
    'VAT': 'in_invoice',
    'KOR': 'in_refund',
    'ZAL': 'in_invoice',
    'ROZ': 'in_invoice',
    'UPR': 'in_invoice',
    'KOR_ZAL': 'in_refund',
    'KOR_ROZ': 'in_refund',
}


class AccountMove(models.Model):
    _inherit = 'account.move'

    x_ksef_p_16 = fields.Boolean(
        string='Cash accounting',
        help='W przypadku dostawy towarów lub świadczenia usług, '
        'w odniesieniu do których obowiązek podatkowy powstaje '
        'zgodnie z art. 19a ust. 5 pkt 1 lub art. 21 ust. 1 ustawy',
    )

    x_ksef_p_17 = fields.Boolean(
        string='Self-billing', help='W przypadku faktur, o których mowa w art. 106d ust. 1 ustawy'
    )

    x_ksef_p_19 = fields.Boolean(
        string='Tax exemption',
        help='Znacznik dostawy towarów lub świadczenia usług zwolnionych od podatku na podstawie art. 43 ust. 1 ustawy'
        ', art. 113 ust. 1 i 9 ustawy albo przepisów wydanych na podstawie art. 82 ust. 3 ustawy lub na '
        'podstawie innych przepisów.',
    )
    x_ksef_p_19a = fields.Char(
        string='Act/regulation provision',
        help='Jeśli pole P_19 równa się "1" - należy wskazać przepis ustawy albo aktu wydanego na podstawie ustawy, '
        'na podstawie którego podatnik stosuje zwolnienie od podatku',
    )
    x_ksef_p_19b = fields.Char(
        string='Directive provision',
        help='Jeśli pole P_19 równa się "1" - należy wskazać przepis dyrektywy 2006/112/WE, '
        'który zwalnia od podatku taką dostawę towarów lub takie świadczenie usług',
    )
    x_ksef_p_19c = fields.Char(
        string='Other legal basis',
        help='Jeśli pole P_19 równa się "1" - należy wskazać inną podstawę prawną wskazującą na to, '
        'że dostawa towarów lub świadczenie usług korzysta ze zwolnienia od podatku',
    )

    # TODO: NoweSrodkiTransportu

    x_ksef_p_pmarzy = fields.Boolean(
        'Margin procedure', help='Znacznik wystąpienia procedur marży, o których mowa w art. 119 lub art. 120 ustawy'
    )

    x_ksef_p_pmarzy_2 = fields.Boolean(
        string='Travel agencies',
        help='Znacznik świadczenia usług turystyki, dla których podstawę opodatkowania stanowi marża, '
        'zgodnie z art. 119 ust. 1 ustawy, '
        'a faktura dokumentująca świadczenie zawiera wyrazy "procedura marży dla biur podróży"',
    )
    x_ksef_p_pmarzy_3_1 = fields.Boolean(
        string='Used goods',
        help='Znacznik dostawy towarów używanych, dla których podstawę opodatkowania stanowi marża, '
        'zgodnie z art. 120 ustawy, '
        'a faktura dokumentująca dostawę zawiera wyrazy "procedura marży - towary używane"',
    )
    x_ksef_p_pmarzy_3_2 = fields.Boolean(
        string='Works of art',
        help='Znacznik dostawy dzieł sztuki, dla których podstawę opodatkowania stanowi marża, '
        'zgodnie z art. 120 ustawy, '
        'a faktura dokumentująca dostawę zawiera wyrazy "procedura marży - dzieła sztuki"',
    )
    x_ksef_p_pmarzy_3_3 = fields.Boolean(
        string='Antiques and collectibles',
        help='Znacznik dostawy przedmiotów kolekcjonerskich i antyków, '
        'dla których podstawę opodatkowania stanowi marża, zgodnie z art. 120 ustawy, '
        'a faktura dokumentująca dostawę zawiera wyrazy "procedura marży - przedmioty kolekcjonerskie i antyki"',
    )

    x_ksef_invoice_reference = fields.Char(string='X KSeF Reference Number', readonly=True, copy=False)
    x_ksef_session_reference = fields.Char(
        string='KSeF Session Reference Number', readonly=True, copy=False, index=True
    )
    x_ksef_session_type = fields.Selection(
        selection=[
            ('interactive', 'Interactive'),
            ('batch', 'Batch'),
        ],
        string='KSeF Session Type',
        readonly=True,
        copy=False,
    )
    x_ksef_show_check_invoice_status_btn = fields.Boolean(
        compute='_x_ksef_compute_show_buttons',
        search='_x_ksef_search_show_check_invoice_status_btn',
    )
    x_ksef_show_resend_btn = fields.Boolean(compute='_x_ksef_compute_show_buttons')
    x_ksef_last_invoice_status = fields.Integer(string='KSeF Last Invoice Status', readonly=True, copy=False)
    x_ksef_invoice_status = fields.Selection(
        selection=[
            ('sent', 'Sent (In Progress)'),
            ('accepted', 'Accepted'),
            ('rejected', 'Rejected'),
        ],
        string='KSeF Invoice Status',
        compute='_x_ksef_compute_invoice_status',
        store=True,
    )

    x_ksef_attachment_file = fields.Binary(copy=False, attachment=True)
    x_ksef_attachment_id = fields.Many2one(
        comodel_name='ir.attachment',
        string='X KSeF Attachment',
        compute=lambda self: self._compute_linked_attachment_id('x_ksef_attachment_id', 'x_ksef_attachment_file'),
        depends=['x_ksef_attachment_file'],
    )

    x_ksef_invoice_date_applicability = fields.Selection(
        selection=[
            ('common', 'A common date of supply or completion of services applicable to the entire invoice.'),
            ('itemized', 'Different delivery or service completion dates for individual goods or services.'),
        ],
        string='KSeF Invoice Date Applicability',
        default='common',
    )

    x_ksef_third_party_ids = fields.One2many('ksef.third_party', 'move_id', string='KSeF Third Parties')

    x_ksef_has_generated_xml = fields.Boolean(
        compute='_x_ksef_compute_has_generated_xml',
    )

    x_ksef_warn_refund_no_reversed_entry = fields.Boolean(
        compute='_x_ksef_compute_warn_refund_no_reversed_entry',
    )

    def x_ksef_is_candidate(self):
        self.ensure_one()
        return (
            self.x_use_ti
            and self.country_code == 'PL'
            and self.is_sale_document()
            and (self.partner_id.is_company or bool(self.partner_id.vat))
        )

    @api.depends(
        'move_type',
        'reversed_entry_id',
        'x_use_ti',
        'country_code',
        'journal_id.type',
        'partner_id.is_company',
        'partner_id.vat',
    )
    def _x_ksef_compute_warn_refund_no_reversed_entry(self):
        for move_id in self:
            move_id.x_ksef_warn_refund_no_reversed_entry = (
                move_id.x_ksef_is_candidate() and move_id.x_is_refund() and not move_id.reversed_entry_id
            )

    @api.depends('edi_document_ids.attachment_id', 'edi_document_ids.edi_format_id')
    def _x_ksef_compute_has_generated_xml(self):
        for move_id in self:
            move_id.x_ksef_has_generated_xml = bool(
                move_id.sudo().edi_document_ids.filtered(
                    lambda ed_id: ed_id.edi_format_id.code == KSEF_CODE and ed_id.attachment_id
                )
            )

    @api.onchange('x_pl_vat_mr_t')
    def _x_ksef_onchange_x_pl_vat_mr_t(self):
        for move_id in self:
            if move_id.x_pl_vat_mr_t:
                move_id.x_ksef_p_pmarzy = True
                move_id.x_ksef_p_pmarzy_2 = True
            else:
                move_id.x_ksef_p_pmarzy_2 = False
                if not any([move_id.x_ksef_p_pmarzy_3_1, move_id.x_ksef_p_pmarzy_3_2, move_id.x_ksef_p_pmarzy_3_3]):
                    move_id.x_ksef_p_pmarzy = False

    @api.onchange('x_ksef_p_pmarzy_2')
    def _x_ksef_onchange_x_ksef_p_pmarzy_2(self):
        for move_id in self:
            if move_id.x_ksef_p_pmarzy_2:
                move_id.x_pl_vat_mr_t = True
                move_id.x_ksef_p_pmarzy = True
            else:
                move_id.x_pl_vat_mr_t = False
                if not any([move_id.x_ksef_p_pmarzy_3_1, move_id.x_ksef_p_pmarzy_3_2, move_id.x_ksef_p_pmarzy_3_3]):
                    move_id.x_ksef_p_pmarzy = False

    def _x_ksef_compute_show_buttons(self):
        for move_id in self:
            move_id.x_ksef_show_check_invoice_status_btn = move_id.x_ksef_invoice_status not in {'accepted', 'rejected'}

            if move_id.x_ksef_session_type == 'interactive':
                move_id.x_ksef_show_check_invoice_status_btn &= bool(move_id.x_ksef_invoice_reference)

            elif move_id.x_ksef_session_type == 'batch':
                move_id.x_ksef_show_check_invoice_status_btn &= bool(move_id.x_ksef_session_reference)

            else:
                move_id.x_ksef_show_check_invoice_status_btn = False

            move_id.x_ksef_show_resend_btn = move_id.x_ksef_last_invoice_status == 450

    def _x_ksef_search_show_check_invoice_status_btn(self, operator, value):
        if operator not in ('=', '!='):
            raise NotImplementedError('Unsupported search operation on x_ksef_show_check_invoice_status_btn')

        want_true = bool(value)

        if operator == '!=':
            want_true = not want_true

        true_domain = [
            ('x_ksef_invoice_status', 'not in', ('accepted', 'rejected')),
            '|',
            '&',
            ('x_ksef_session_type', '=', 'interactive'),
            ('x_ksef_invoice_reference', '!=', False),
            '&',
            ('x_ksef_session_type', '=', 'batch'),
            ('x_ksef_session_reference', '!=', False),
        ]

        return true_domain if want_true else ['!'] + true_domain

    @api.depends('x_ksef_last_invoice_status')
    def _x_ksef_compute_invoice_status(self):
        for move_id in self:
            if not move_id.x_ksef_last_invoice_status:
                move_id.x_ksef_invoice_status = None
                continue

            if move_id.x_ksef_last_invoice_status < 200:
                move_id.x_ksef_invoice_status = 'sent'

            elif move_id.x_ksef_last_invoice_status == 200:
                move_id.x_ksef_invoice_status = 'accepted'

            else:
                move_id.x_ksef_invoice_status = 'rejected'

    def x_ksef_check_interactive_invoice_status(self, client=None):
        if not self:
            return

        self.company_id.ensure_one()

        if client is None:
            client = self.company_id.x_ksef_get_authenticated_client()

        for invoice_id in self:
            try:
                invoice_status = client.get_session_invoice_status(
                    invoice_reference=invoice_id.x_ksef_invoice_reference,
                    session_reference=invoice_id.x_ksef_session_reference,
                )

            except KsefClientError as error:
                self.company_id.x_ksef_notify_admins(
                    note=invoice_id.x_ksef_format_error_html(
                        error_title=_('Error while checking invoice status'),
                        error=error,
                    ),
                )
                raise ValidationError(_('Error while checking invoice status: %s', str(error))) from error

            invoice_id.x_ksef_last_invoice_status = invoice_status.status.code

            if invoice_id.x_ksef_last_invoice_status == KsefStatusCode.OK:
                invoice_id.x_pl_ksef_invoice_number = invoice_status.ksef_number
            elif invoice_id.x_ksef_last_invoice_status > KsefStatusCode.OK:
                self.company_id.x_ksef_notify_admins(
                    note=invoice_id.x_ksef_format_error_html(
                        error_title=_('Got invalid invoice status from KSeF'),
                        error=f'{invoice_id.x_ksef_last_invoice_status} - {invoice_status.status.description}',
                    ),
                )

            if upo_download_url := invoice_status.upo_download_url:
                invoice_id.message_post(
                    body=_(
                        'KSeF Invoice status: %s - %s',
                        invoice_status.status.description,
                        Markup(_('<a href="%s" target="_blank">Download UPO</a>', upo_download_url)),
                    )
                )

            else:
                invoice_id.message_post(
                    body=_(
                        'KSeF Invoice status: %s - %s',
                        invoice_id.x_ksef_last_invoice_status,
                        invoice_status.status.description,
                    )
                )

    def x_ksef_check_batch_invoice_status(self, client=None):
        if not self:
            return

        self.company_id.ensure_one()

        if client is None:
            client = self.company_id.x_ksef_get_authenticated_client()

        for session_reference in set(self.mapped('x_ksef_session_reference')):
            session_invoice_ids = self.search(
                [
                    ('x_ksef_session_reference', '=', session_reference),
                    ('x_ksef_show_check_invoice_status_btn', '=', True),
                ],
            )

            try:
                session_invoices = client.get_all_session_invoices(session_reference=session_reference)

            except KsefClientError as error:
                self.company_id.x_ksef_notify_admins(
                    note=session_invoice_ids.x_ksef_format_error_html(
                        error_title=_('Error while checking invoice status'),
                        error=error,
                    ),
                )
                raise ValidationError(_('Error while checking invoice status: %s', str(error))) from error

            invoice_file_name_response_map = {invoice.invoice_file_name: invoice for invoice in session_invoices}

            for invoice_id in session_invoice_ids:
                invoice_status = invoice_file_name_response_map.get(invoice_id.x_ksef_get_invoice_file_name())

                if not invoice_status:
                    _logger.warning(
                        'Missing status response inside session %s for invoice %s', session_reference, invoice_id
                    )
                    continue

                invoice_id.write(
                    {
                        'x_ksef_invoice_reference': invoice_status.reference_number,
                        'x_pl_ksef_invoice_number': invoice_status.ksef_number,
                        'x_ksef_last_invoice_status': invoice_status.status.code,
                    }
                )

                if invoice_status.status.code > KsefStatusCode.OK:
                    self.company_id.x_ksef_notify_admins(
                        note=invoice_id.x_ksef_format_error_html(
                            error_title=_('Got invalid invoice status from KSeF'),
                            error=invoice_status.status,
                        ),
                    )

                if upo_download_url := invoice_status.upo_download_url:
                    invoice_id.message_post(
                        body=_(
                            'KSeF Invoice status: %s - %s',
                            invoice_status.status.description,
                            Markup(_('<a href="%s" target="_blank">Download UPO</a>', upo_download_url)),
                        )
                    )

                else:
                    invoice_id.message_post(
                        body=_(
                            'KSeF Invoice status: %s - %s',
                            invoice_id.x_ksef_last_invoice_status,
                            invoice_status.status.description,
                        )
                    )

    def x_ksef_check_invoice_status(self, client=None):
        self.filtered(
            lambda invoice_id: invoice_id.x_ksef_session_type == 'interactive'
        ).x_ksef_check_interactive_invoice_status(
            client=client,
        )

        self.filtered(lambda invoice_id: invoice_id.x_ksef_session_type == 'batch').x_ksef_check_batch_invoice_status(
            client=client,
        )

    @api.model
    def _x_ksef_get_invoice_batch_import_queue_key(self, company_id):
        return f'ksef_invoice_batch_import_queue_{company_id.id}'

    @api.model
    def _x_ksef_get_invoice_batch_import_state_key(self, company_id, batch_ref):
        return f'ksef_invoice_batch_import_state_{company_id.id}_{batch_ref}'

    @api.model
    def _x_ksef_get_invoice_batch_import_eligible_company_ids(self):
        return self.env['res.company'].search(
            [
                ('x_ksef_settings_id', '!=', False),
                ('x_ksef_purchase_journal_id', '!=', False),
            ]
        )

    @api.model
    def _x_ksef_cron_check_invoice_status(self):
        for company_id in self.env['res.company'].search([('x_ksef_settings_id', '!=', False)]):
            self.env['account.move'].search(
                [
                    ('company_id', '=', company_id.id),
                    ('x_ksef_show_check_invoice_status_btn', '=', True),
                ]
            ).x_ksef_check_invoice_status(client=company_id.x_ksef_get_authenticated_client())

            self.env.cr.commit()

    @api.model
    def _x_ksef_cron_start_invoice_batch_import(self):
        company_ids = self._x_ksef_get_invoice_batch_import_eligible_company_ids()

        self._x_ksef_start_invoice_batch_import(company_ids=company_ids)
        _logger.info('KSeF cron started invoice batch import for companies %s.', company_ids)

        self.env.ref('trilab_ksef.cron_check_invoice_batch_import_status')._trigger(
            at=fields.Datetime.add(fields.Datetime.now(), minutes=1)
        )

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

    def _x_ksef_create_report_attachment(self, report_id):
        self.ensure_one()

        try:
            pdf_content = report_id._render_qweb_pdf(report_id, self.id)[0]
        except ValidationError:
            _logger.exception(f'Could not render KSeF Invoice report for {self}')
            return

        if report_id.print_report_name:
            report_name = safe_eval(report_id.print_report_name, {'object': self, 'time': time})
            filename = f'{report_name}.pdf'

        else:
            filename = f'{self.x_pl_ksef_invoice_number}.pdf'

        self.message_main_attachment_id = (
            self.sudo()
            .env['ir.attachment']
            .create(
                {
                    'name': filename,
                    'type': 'binary',
                    'raw': pdf_content,
                    'res_model': 'account.move',
                    'res_id': self.id,
                    'mimetype': 'application/pdf',
                }
            )
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
                    icp_id.set_param(state_key, None)
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
                    _logger.exception('KSeF batch %s import error for company %s', batch_ref, company_id.id)
                    company_id.x_ksef_notify_admins(
                        note=self.env['account.move'].x_ksef_format_error_html(
                            error_title=_(
                                'KSeF batch %s import error',
                                batch_ref,
                            ),
                            error=error,
                        ),
                    )
                    icp_id.set_param(state_key, None)
                    continue

                if export_result is None:
                    icp_id.set_param(state_key, None)
                    continue

                move_id = self.env['account.move']

                try:
                    for filename, invoice_xml in export_result.invoices:
                        if self.env['ir.attachment'].search_count(
                            [
                                ('name', '=', filename),
                                ('res_model', '=', 'account.move'),
                                ('res_field', '=', 'x_ksef_attachment_file'),
                            ],
                            limit=1,
                        ):
                            _logger.debug('Vendor bill already exists: %s', filename)
                            continue

                        try:
                            xml_tree = etree.fromstring(invoice_xml.encode())
                            move_type = self._x_ksef_get_vendor_move_type(xml_tree)
                            partner_id = self._x_ksef_get_vendor_partner_id(xml_tree, company_id)
                            journal_id = (
                                partner_id.with_company(company_id).x_ksef_purchase_journal_id
                                or company_id.x_ksef_purchase_journal_id
                            )
                        except etree.ParseError:
                            move_type = 'in_invoice'
                            partner_id = None
                            journal_id = (
                                company_id.x_ksef_fallback_purchase_journal_id or company_id.x_ksef_purchase_journal_id
                            )

                        move_id = (
                            self.sudo()
                            .with_company(company_id)
                            .with_context(
                                default_move_type=move_type,
                                default_journal_id=journal_id,
                                x_ksef_partner_id=partner_id,
                            )
                            .create({'x_pl_ksef_invoice_number': filename.removesuffix('.xml')})
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
                        move_id.invalidate_recordset(fnames=['x_ksef_attachment_id', 'x_ksef_attachment_file'])
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

                        move_id.with_context(disable_onchange_name_predictive=True)._extend_with_attachments(
                            move_id.x_ksef_attachment_id, new=True
                        )
                        move_id._x_ksef_create_report_attachment(report_id)
                        _logger.debug('Created %s from %s', move_id.name, filename)

                except KsefInvoiceBatchExportError as error:
                    _logger.exception(
                        'KSeF batch %s import error for company %s',
                        batch_ref,
                        company_id.id,
                    )

                    company_id.x_ksef_notify_admins(
                        note=move_id.x_ksef_format_error_html(
                            error_title=_(
                                'KSeF batch %s import error',
                                batch_ref,
                            ),
                            error=error,
                        ),
                    )

                    continue

                finally:
                    icp_id.set_param(state_key, None)

                company_id.x_ksef_purchase_invoice_sync_date = max(
                    company_id.x_ksef_purchase_invoice_sync_date or datetime.min,
                    export_result.permanent_storage_hwm_date.astimezone(UTC).replace(tzinfo=None),
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

        self._x_ksef_check_invoice_batch_import_status(company_ids=company_ids)
        _logger.info('KSeF cron checked invoice batch import status for companies %s.', company_ids)

    # noinspection PyMethodMayBeStatic
    def _x_ksef_is_vendor_bill_xml(self, file_xml_tree):
        if (form_code := next(iter(file_xml_tree.xpath('.//tns:KodFormularza', namespaces=NSMAP)), None)) is not None:
            return form_code.attrib.get('kodSystemowy') == 'FA (3)' and form_code.attrib.get('wersjaSchemy') == '1-0E'

        return False

    def _x_ksef_search_product_for_import(self, ksef_fa_wiersz):
        return self.env['product.product']._retrieve_product(
            name=ksef_fa_wiersz.P_7.text,
            barcode=ksef_fa_wiersz.GTIN.text,
            default_code=ksef_fa_wiersz.Indeks.text,
        )

    def _x_ksef_search_tax_for_import(self, amount_code, price_included):
        self.ensure_one()

        return self.env['account.tax'].search(
            [
                ('company_id', '=', self.company_id.id),
                ('x_ksef_amount', '=', amount_code),
                ('amount_type', '=', 'percent'),
                ('type_tax_use', '=', 'purchase'),
                ('price_include', '=', price_included),
            ],
            limit=1,
        )

    # noinspection PyMethodMayBeStatic
    def _x_ksef_parse_annotations(self, ksef_fa):
        annotations_data = {}

        if (annotations_el := ksef_fa.Adnotacje) is None:
            return annotations_data

        for annotation_field in ('P_16', 'P_17'):
            if (annotation_value := getattr(annotations_el, annotation_field, None)) is not None:
                field_name = f'x_ksef_{annotation_field.lower()}'
                annotations_data[field_name] = annotation_value == 1

        if (p18_value := annotations_el.P_18) is not None:
            annotations_data['x_pl_vat_reverse_charge'] = p18_value == 1

        if (p18a_value := annotations_el.P_18A) is not None:
            annotations_data['x_pl_vat_mpp'] = p18a_value == 1

        if (zwolnienie_el := annotations_el.Zwolnienie) is not None:
            if (p19_value := zwolnienie_el.P_19) is not None:
                annotations_data['x_ksef_p_19'] = p19_value == 1

                if annotations_data['x_ksef_p_19']:
                    for p19_subfield in ('P_19A', 'P_19B', 'P_19C'):
                        if (p19_sub_value := getattr(zwolnienie_el, p19_subfield, None)) is not None:
                            field_name = f'x_ksef_{p19_subfield.lower()}'
                            annotations_data[field_name] = p19_sub_value.text
                            break

        if (p23_value := annotations_el.P_23) is not None:
            annotations_data['x_pl_vat_tt_wnt'] = p23_value == 1

        if (pmarzy_el := annotations_el.PMarzy) is not None:
            if p_pmarzy_value := pmarzy_el.P_PMarzy.text:
                annotations_data['x_ksef_p_pmarzy'] = p_pmarzy_value == 1

                if annotations_data['x_ksef_p_pmarzy']:
                    for pmarzy_subfield in ['P_PMarzy_2', 'P_PMarzy_3_1', 'P_PMarzy_3_2', 'P_PMarzy_3_3']:
                        if (pmarzy_sub_value := getattr(pmarzy_el, pmarzy_subfield, None)) is not None:
                            field_name = f'x_ksef_{pmarzy_subfield.lower()}'
                            annotations_data[field_name] = pmarzy_sub_value == 1
                            if pmarzy_subfield == 'P_PMarzy_2' and annotations_data[field_name]:
                                annotations_data['x_pl_vat_mr_t'] = True
                            break

        return annotations_data

    def _x_ksef_parse_invoice_line(self, ksef_fa_wiersz, messages_to_log):
        line_vals = {}

        if description := ksef_fa_wiersz.P_7.text:
            line_vals['name'] = description

        if product_id := self._x_ksef_search_product_for_import(ksef_fa_wiersz):
            line_vals['product_id'] = product_id.id

        else:
            messages_to_log.append(_("The product '%s' could not be found.", line_vals.get('name')))

        line_vals['quantity'] = float(ksef_fa_wiersz.P_8B or 0)

        if price_unit_untaxed := ksef_fa_wiersz.P_9A.text:
            line_vals['price_unit'] = float(price_unit_untaxed)
            tax_price_included = False

        elif price_unit := ksef_fa_wiersz.P_9B.text:
            tax_price_included = True
            line_vals['price_unit'] = float(price_unit)

        else:
            tax_price_included = False
            messages_to_log.append(_("The price unit for the product '%s' could not be found.", line_vals.get('name')))

        if discount_amount := ksef_fa_wiersz.P_10.text:
            price_unit = line_vals.get('price_unit', 0.0)

            if not self.currency_id.is_zero(price_unit):
                line_vals['discount'] = float(discount_amount) / price_unit * 100

        if (tax_amount := ksef_fa_wiersz.P_12.text) and (
            tax_id := self._x_ksef_search_tax_for_import(amount_code=tax_amount, price_included=tax_price_included)
        ):
            line_vals['tax_ids'] = [fields.Command.set(tax_id.ids)]
        elif tax_amount:
            if tax_price_included:
                messages_to_log.append(
                    _(
                        'Could not retrieve the tax: %s%% "Included in Price" for line "%s".',
                        tax_amount,
                        line_vals.get('name', ''),
                    )
                )

            else:
                messages_to_log.append(
                    _(
                        'Could not retrieve the tax: %s%% not "Included in Price" for line "%s".',
                        tax_amount,
                        line_vals.get('name', ''),
                    )
                )

        return line_vals

    def _x_ksef_parse_invoice_lines(self, ksef_fa, move_type, messages_to_log):
        invoice_lines_vals = []

        if move_type != 'in_invoice':
            return invoice_lines_vals

        for ksef_fa_wiersz in ksef_fa.FaWiersz:
            invoice_lines_vals.append(self._x_ksef_parse_invoice_line(ksef_fa_wiersz, messages_to_log))

        return invoice_lines_vals

    @staticmethod
    def _x_ksef_get_vendor_move_type(xml_tree):
        return VENDOR_MOVE_TYPE_MAPPING.get(
            find_xml_value('.//tns:RodzajFaktury', xml_tree, namespaces=NSMAP), 'in_invoice'
        )

    @api.model
    def _x_ksef_get_vendor_partner_id(self, xml_tree, company_id):
        if partner_vat := find_xml_value('.//tns:Podmiot1/tns:DaneIdentyfikacyjne/tns:NIP', xml_tree, namespaces=NSMAP):
            return self.env['res.partner'].search(
                [
                    ('vat', '=ilike', f'%{partner_vat}'),
                    ('company_id', 'in', [company_id.id, False]),
                ],
                limit=1,
            )

        return None

    # noinspection PyUnusedLocal
    def _x_ksef_import_vendor_invoice(self, invoice_id, file_data, is_new):
        ksef_faktura = parse_ksef_xml(file_data['content'])  # `Faktura` XML tag

        with self._get_edi_creation() as self:
            messages = []

            partner_id = None
            if partner_id := self.env.context.get('x_ksef_partner_id'):
                self.partner_id = partner_id
            elif not partner_id and (partner_vat := ksef_faktura.Podmiot1.DaneIdentyfikacyjne.NIP.text):
                if partner_id := self.env['res.partner'].search(
                    [
                        ('vat', '=ilike', f'%{partner_vat}'),
                        ('company_id', 'in', [self.company_id.id, False]),
                    ],
                    limit=1,
                ):
                    self.partner_id = partner_id
                else:
                    self.partner_id = self.env['res.partner'].create(
                        {
                            'name': ksef_faktura.Podmiot1.DaneIdentyfikacyjne.Nazwa.text,
                            'vat': partner_vat,
                            'is_company': True,
                        }
                    )

                    messages.append(
                        _(
                            'A vendor with a matching Tax ID was not found. '
                            'One with the corresponding details was created.'
                        )
                    )
            else:
                raise UserError(_('Could not find a partner data in KSeF XML.'))

            ksef_fa = ksef_faktura.Fa

            if invoice_date := ksef_fa.P_1.text:
                self.invoice_date = dateutil.parser.parse(invoice_date, ignoretz=True).date()

            if vat_date := ksef_faktura.Naglowek.DataWytworzeniaFa.text:
                self.pl_vat_date = dateutil.parser.parse(vat_date, ignoretz=True).date()

            if invoice_sale_date := ksef_fa.P_6.text:
                self.x_invoice_sale_date = dateutil.parser.parse(invoice_sale_date, ignoretz=True).date()

            if invoice_date_due := min(
                (date.fromisoformat(_tp.Termin.text) for _tp in ksef_fa.Platnosc.TerminPlatnosci if _tp.Termin.text),
                default=None,
            ):
                self.invoice_date_due = invoice_date_due

            if invoice_number := ksef_fa.P_2.text:
                self.ref = invoice_number

            if currency_code := ksef_fa.KodWaluty.text:
                self.currency_id = self.env['res.currency'].search([('name', '=', currency_code)], limit=1)

            self.update(self._x_ksef_parse_annotations(ksef_fa))

            self.invoice_line_ids = [
                fields.Command.create(vals)
                for vals in self._x_ksef_parse_invoice_lines(ksef_fa, self.move_type, messages)
            ]

            self.sudo().message_post(body=Markup('<br/>').join(messages))

            return True

    def _get_edi_decoder(self, file_data, new=False):
        if file_data['type'] == 'xml' and self._x_ksef_is_vendor_bill_xml(file_data['xml_tree']):
            return self._x_ksef_import_vendor_invoice

        return super()._get_edi_decoder(file_data, new=new)

    def x_ksef_is_online(self) -> bool:
        self.ensure_one()
        return bool(self.x_pl_ksef_invoice_number)

    def _x_ksef_generate_qr_pair(self, qr_url: str) -> tuple[str, str]:
        try:
            barcode = self.env['ir.actions.report'].barcode(
                **{
                    'barcode_type': 'QR',
                    'width': 200,
                    'height': 200,
                    'humanreadable': 1,
                    'value': qr_url,
                }
            )

        except (ValueError, AttributeError) as error:
            raise ValidationError(_('Could not generate KSeF QR code.')) from error

        return image_data_uri(base64.b64encode(barcode)), qr_url

    def x_ksef_generate_qr_code_url_pair(self) -> tuple[tuple[str, str], ...] | None:
        self.ensure_one()

        ksef_edi_document_id = self.edi_document_ids.sudo().filtered(
            lambda doc_id: doc_id.edi_format_id.code == KSEF_CODE
        )

        partner_id = self.company_id.partner_id

        if self.x_ksef_attachment_id:
            partner_id = self.partner_id

        if (
            not (ksef_edi_document_id.attachment_id or self.x_ksef_attachment_id)
            or not partner_id.vat
            or not self.invoice_date
        ):
            return None

        nip = partner_id.x_get_pl_vat(raise_exception=True)

        ksef_url = KsefClient.build_invoice_verification_url(
            base_qr_url=self.company_id.x_ksef_settings_id.qr_code_url,
            nip=nip,
            issue_date=self.invoice_date,
            invoice_xml=(ksef_edi_document_id.attachment_id or self.x_ksef_attachment_id).raw,
        )

        if self.x_ksef_is_online():
            return (self._x_ksef_generate_qr_pair(ksef_url),)

        if (
            not self.company_id.x_ksef_plain_verification_link_certificate_datas
            or not self.company_id.x_ksef_plain_verification_link_private_key_datas
            or not self.company_id.x_ksef_plain_verification_link_private_key_password
        ):
            raise ValidationError(_('KSeF verification link certificate and private key are not configured.'))

        ksef_certificate_url = KsefClient.build_certificate_verification_url(
            base_qr_url=self.company_id.x_ksef_settings_id.qr_code_url,
            context_value=nip,
            seller_nip=nip,
            certificate_pem=base64.b64decode(self.company_id.x_ksef_plain_verification_link_certificate_datas),
            private_key_pem=base64.b64decode(self.company_id.x_ksef_plain_verification_link_private_key_datas),
            invoice_xml=ksef_edi_document_id.attachment_id.raw,
            private_key_password=self.company_id.x_ksef_plain_verification_link_private_key_password.encode(),
        )

        return self._x_ksef_generate_qr_pair(ksef_url), self._x_ksef_generate_qr_pair(ksef_certificate_url)

    def x_ksef_get_invoice_file_name(self):
        self.ensure_one()
        return f'{self.id}.xml'

    def _x_ksef_post_edi(self):
        # Note: method logic comes from `_post` - addons/account_edi/models/account_move.py
        edi_document_vals_list = []

        for move_id in self:
            for edi_format_id in move_id.journal_id.edi_format_ids:
                if not edi_format_id.with_context(x_ksef_skip_resend=True)._get_move_applicability(move_id):
                    continue

                if errors := edi_format_id._check_move_configuration(move_id):
                    raise UserError(_('Invalid invoice configuration:\n%s', '\n'.join(errors)))

                if existing_edi_document := move_id.edi_document_ids.filtered(
                    lambda d_id: d_id.edi_format_id == edi_format_id
                ):
                    existing_edi_document.sudo().write(
                        {
                            'state': 'to_send',
                            'attachment_id': False,
                        }
                    )

                else:
                    edi_document_vals_list.append(
                        {
                            'edi_format_id': edi_format_id.id,
                            'move_id': move_id.id,
                            'state': 'to_send',
                        }
                    )

        self.env['account.edi.document'].create(edi_document_vals_list)
        self.edi_document_ids._process_documents_no_web_services()

        return self

    def x_ksef_resend_invoice(self):
        self.ensure_one()

        edi_format_id = self.journal_id.edi_format_ids.filtered(lambda ef_id: ef_id.code == KSEF_CODE)

        if not edi_format_id:
            raise UserError(_('No KSeF EDI format found on the journal.'))

        if ksef_edi_doc_ids := self.edi_document_ids.sudo().filtered(
            lambda doc_id: doc_id.edi_format_id == edi_format_id
        ):
            _logger.info(f'Deleting KSeF EDI documents for {self} with attachments {ksef_edi_doc_ids.attachment_id}')
            ksef_edi_doc_ids.unlink()

        new_doc_id = (
            self.env['account.edi.document']
            .sudo()
            .create(
                {
                    'edi_format_id': edi_format_id.id,
                    'move_id': self.id,
                    'state': 'to_send',
                }
            )
        )

        new_doc_id._process_documents_no_web_services()

    def _x_post_wo_validation(self, soft=True):
        posted_ids = super()._x_post_wo_validation(soft=soft)
        self._x_ksef_post_edi()

        return posted_ids

    def _post(self, soft=True):
        ti_move_ids = self.filtered('x_use_ti').with_context(
            skip_account_edi_cron_trigger=True,
            x_ksef_skip_resend=True,
        )
        return super(AccountMove, ti_move_ids)._post(soft=soft) | super(AccountMove, self - ti_move_ids)._post(soft=soft)

    def x_ksef_get_invoice_line_ids(self):
        self.ensure_one()

        invoice_line_ids = self.invoice_line_ids.filtered(lambda l_id: l_id.display_type == 'product')

        if self.x_advance_invoices_ids:
            invoice_line_ids = invoice_line_ids.filtered(lambda l_id: not l_id.is_downpayment)

        if self.company_id.x_ksef_enable_ignore_zero_amount_lines:
            invoice_line_ids = invoice_line_ids.filtered(
                lambda l_id: not float_is_zero(
                    l_id.price_unit, self.env['decimal.precision'].precision_get('Product Price')
                )
            )

        return invoice_line_ids.sorted(
            key=lambda l_id: (-l_id.sequence, l_id.date, l_id.move_name, -l_id.id),
            reverse=True,
        )

    def x_ksef_format_error_html(self, error_title, error):
        invoices = Markup().join(
            Markup('<li><a href="#" data-oe-model="account.move" data-oe-id="%s">Invoice</a></li>') % invoice_id.id
            for invoice_id in self
        )
        return Markup('%s<br/><ul>%s</ul><br/><pre>%s</pre>') % (error_title, invoices, str(error))

    def x_ksef_unlink_to_send_edi_documents(self):
        deleted = 0
        moves = len(self)

        for move_id in self:
            edi_document_to_send_id = move_id.edi_document_ids.filtered(
                lambda ed_id: ed_id.edi_format_id.code == KSEF_CODE and ed_id.state == 'to_send'
            )

            if edi_document_to_send_id:
                move_id.message_post(body=_('KSeF EDI Document deleted before sending.'))
                edi_document_to_send_id.unlink()
                deleted += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'info',
                'sticky': False,
                'message': _('Unlinked %s KSeF EDI Document(s) from %s invoice(s).', deleted, moves),
            },
        }
