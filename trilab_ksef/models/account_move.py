import base64
import logging
from typing import Optional, Tuple

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import Form
from odoo.tools import float_is_zero, image_data_uri
from odoo.tools.safe_eval import dateutil, safe_eval, time

from .account_edi_format import KSEF_CODE, NS
from .ksef_client import KsefClient, KsefClientError, KsefStatusCode
from .utils import find_xml_value

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
        string='P_16',
        help='W przypadku dostawy towarów lub świadczenia usług, '
        'w odniesieniu do których obowiązek podatkowy powstaje '
        'zgodnie z art. 19a ust. 5 pkt 1 lub art. 21 ust. 1 ustawy',
    )

    x_ksef_p_17 = fields.Boolean(string='P_17', help='W przypadku faktur, o których mowa w art. 106d ust. 1 ustawy')

    x_ksef_p_18 = fields.Boolean(
        string='P_18',
        help='W przypadku dostawy towarów lub wykonania usługi, '
        'dla których obowiązanym do rozliczenia podatku od wartości dodanej '
        'lub podatku o podobnym charakterze jest nabywca towaru lub usługi',
    )
    x_ksef_p_18a = fields.Boolean(
        string='P_18A',
        help='W przypadku faktur, w których kwota należności ogółem przekracza kwotę 15 000 zł '
        'lub jej równowartość wyrażoną w walucie obcej, obejmujących dokonaną na rzecz podatnika dostawę towarów '
        'lub świadczenie usług, o których mowa w załączniku nr 15 do ustawy',
    )

    x_ksef_p_19 = fields.Boolean(
        string='P_19',
        help='Znacznik dostawy towarów lub świadczenia usług zwolnionych od podatku na podstawie art. 43 ust. 1 ustawy'
        ', art. 113 ust. 1 i 9 ustawy albo przepisów wydanych na podstawie art. 82 ust. 3 ustawy lub na '
        'podstawie innych przepisów.',
    )
    x_ksef_p_19a = fields.Char(
        string='P_19A',
        help='Jeśli pole P_19 równa się "1" - należy wskazać przepis ustawy albo aktu wydanego na podstawie ustawy, '
        'na podstawie którego podatnik stosuje zwolnienie od podatku',
    )
    x_ksef_p_19b = fields.Char(
        string='P_19B',
        help='Jeśli pole P_19 równa się "1" - należy wskazać przepis dyrektywy 2006/112/WE, '
        'który zwalnia od podatku taką dostawę towarów lub takie świadczenie usług',
    )
    x_ksef_p_19c = fields.Char(
        string='P_19C',
        help='Jeśli pole P_19 równa się "1" - należy wskazać inną podstawę prawną wskazującą na to, '
        'że dostawa towarów lub świadczenie usług korzysta ze zwolnienia od podatku',
    )

    # TODO: NoweSrodkiTransportu

    x_ksef_p_23 = fields.Boolean(
        string='P_23',
        help='W przypadku faktur wystawianych w procedurze uproszczonej przez drugiego w kolejności podatnika, '
        'o którym mowa w art. 135 ust. 1 pkt 4 lit. b i c oraz ust. 2 ustawy, zawierającej adnotację, '
        'o której mowa w art. 136 ust. 1 pkt 1 ustawy i stwierdzenie, o którym mowa w art. 136 ust. 1 pkt 2 ustawy',
    )

    x_ksef_p_pmarzy = fields.Boolean(
        'P_PMarzy', help='Znacznik wystąpienia procedur marży, o których mowa w art. 119 lub art. 120 ustawy'
    )

    x_ksef_p_pmarzy_2 = fields.Boolean(
        string='P_PMarzy_2',
        help='Znacznik świadczenia usług turystyki, dla których podstawę opodatkowania stanowi marża, '
        'zgodnie z art. 119 ust. 1 ustawy, '
        'a faktura dokumentująca świadczenie zawiera wyrazy "procedura marży dla biur podróży"',
    )
    x_ksef_p_pmarzy_3_1 = fields.Boolean(
        string='P_PMarzy_3_1',
        help='Znacznik dostawy towarów używanych, dla których podstawę opodatkowania stanowi marża, '
        'zgodnie z art. 120 ustawy, '
        'a faktura dokumentująca dostawę zawiera wyrazy "procedura marży - towary używane"',
    )
    x_ksef_p_pmarzy_3_2 = fields.Boolean(
        string='P_PMarzy_3_2',
        help='Znacznik dostawy dzieł sztuki, dla których podstawę opodatkowania stanowi marża, '
        'zgodnie z art. 120 ustawy, '
        'a faktura dokumentująca dostawę zawiera wyrazy "procedura marży - dzieła sztuki"',
    )
    x_ksef_p_pmarzy_3_3 = fields.Boolean(
        string='P_PMarzy_3_3',
        help='Znacznik dostawy przedmiotów kolekcjonerskich i antyków, '
        'dla których podstawę opodatkowania stanowi marża, zgodnie z art. 120 ustawy, '
        'a faktura dokumentująca dostawę zawiera wyrazy "procedura marży - przedmioty kolekcjonerskie i antyki"',
    )

    x_ksef_invoice_reference = fields.Char(string='KSeF Reference Number', readonly=True, copy=False)
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
        string='KSeF Attachment',
        compute='_x_ksef_compute_linked_attachment_id',
    )

    x_ksef_invoice_date_applicability = fields.Selection(
        selection=[
            ('common', 'A common date of supply or completion of services applicable to the entire invoice.'),
            ('itemized', 'Different delivery or service completion dates for individual goods or services.'),
        ],
        string='KSeF Invoice Date Applicability',
        default='common',
    )

    @api.depends('x_ksef_attachment_file')
    def _x_ksef_compute_linked_attachment_id(self):
        attachment_ids = self.env['ir.attachment'].search(
            [('res_model', '=', self._name), ('res_id', 'in', self.ids), ('res_field', '=', 'x_ksef_attachment_file')]
        )
        move_vals = {att.res_id: att for att in attachment_ids}

        for move_id in self:
            move_id.x_ksef_attachment_id = move_vals.get(move_id._origin.id, False)

    def _x_ksef_compute_show_buttons(self):
        for move_id in self:
            move_id.x_ksef_show_check_invoice_status_btn = move_id.x_ksef_invoice_status not in {'accepted', 'rejected'}

            if move_id.x_ksef_session_type == 'interactive':
                move_id.x_ksef_show_check_invoice_status_btn &= bool(move_id.x_ksef_invoice_reference)

            elif move_id.x_ksef_session_type == 'batch':
                move_id.x_ksef_show_check_invoice_status_btn &= bool(move_id.x_ksef_session_reference)

            else:
                move_id.x_ksef_show_check_invoice_status_btn = False

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
                raise ValidationError(_('Error while checking invoice status: %s', str(error))) from error

            invoice_id.x_ksef_last_invoice_status = invoice_status.status.code

            if invoice_id.x_ksef_last_invoice_status == KsefStatusCode.OK:
                invoice_id.x_pl_ksef_invoice_number = invoice_status.ksef_number

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
            session_invoice_ids = self.search([('x_ksef_session_reference', '=', session_reference)])

            try:
                session_status_response = client.get_session_invoices(
                    session_reference=session_reference,
                )

            except KsefClientError as error:
                raise ValidationError(_('Error while checking invoice status: %s', str(error))) from error

            invoice_file_name_response_map = {
                invoice.invoice_file_name: invoice for invoice in session_status_response['invoices']
            }

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

    def x_ksef_check_invoice_status(self, client=None):
        self.filtered(
            lambda invoice_id: invoice_id.x_ksef_session_type == 'interactive'
        ).x_ksef_check_interactive_invoice_status(
            client=client,
        )

        self.filtered(lambda invoice_id: invoice_id.x_ksef_session_type == 'batch').x_ksef_check_batch_invoice_status(
            client=client,
        )

    def _x_ksef_create_report_attachment(self, report_id):
        self.ensure_one()

        pdf_content = report_id._render_qweb_pdf(self.ids)[0]

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

    def _x_ksef_search_product_for_import(self, invoice_line_node):
        return self.env['product.product']._x_ksef_retrieve_product(
            name=find_xml_value('.//tns:P_7', invoice_line_node, namespaces=NS),
            barcode=find_xml_value('.//tns:GTIN', invoice_line_node, namespaces=NS),
            default_code=find_xml_value('.//tns:Indeks', invoice_line_node, namespaces=NS),
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
    def _x_ksef_parse_annotations(self, xml_tree):
        annotations_data = {}

        if not (annotations_el := xml_tree.xpath('.//tns:Adnotacje', namespaces=NS)):
            return annotations_data

        annotations_el = annotations_el[0]

        for annotation_field in ('P_16', 'P_17', 'P_18', 'P_18A'):
            if annotation_value := find_xml_value(f'.//tns:{annotation_field}', annotations_el, namespaces=NS):
                field_name = f'x_ksef_{annotation_field.lower()}'
                annotations_data[field_name] = annotation_value == '1'

        if zwolnienie_nodes := annotations_el.xpath('.//tns:Zwolnienie', namespaces=NS):
            zwolnienie_el = zwolnienie_nodes[0]
            if p19_value := find_xml_value('.//tns:P_19', zwolnienie_el, namespaces=NS):
                annotations_data['x_ksef_p_19'] = p19_value == '1'

                if annotations_data['x_ksef_p_19']:
                    for p19_subfield in ('P_19A', 'P_19B', 'P_19C'):
                        if p19_sub_value := find_xml_value(f'.//tns:{p19_subfield}', zwolnienie_el, namespaces=NS):
                            field_name = f'x_ksef_{p19_subfield.lower()}'
                            annotations_data[field_name] = p19_sub_value
                            break

        if p23_value := find_xml_value('.//tns:P_23', annotations_el, namespaces=NS):
            annotations_data['x_ksef_p_23'] = p23_value == '1'

        if pmarzy_nodes := annotations_el.xpath('.//tns:PMarzy', namespaces=NS):
            pmarzy_el = pmarzy_nodes[0]
            if p_pmarzy_value := find_xml_value('.//tns:P_PMarzy', pmarzy_el, namespaces=NS):
                annotations_data['x_ksef_p_pmarzy'] = p_pmarzy_value == '1'

                if annotations_data['x_ksef_p_pmarzy']:
                    for pmarzy_subfield in ('P_PMarzy_2', 'P_PMarzy_3_1', 'P_PMarzy_3_2', 'P_PMarzy_3_3'):
                        if pmarzy_sub_value := find_xml_value(f'.//tns:{pmarzy_subfield}', pmarzy_el, namespaces=NS):
                            field_name = f'x_ksef_{pmarzy_subfield.lower()}'
                            annotations_data[field_name] = pmarzy_sub_value == '1'
                            break

        return annotations_data

    def _x_ksef_parse_invoice_lines(self, xml_tree, move_type, message_to_log):
        invoice_lines_vals = []

        if move_type != 'in_invoice':
            return invoice_lines_vals

        for invoice_line in xml_tree.xpath('.//tns:FaWiersz', namespaces=NS):
            line_vals = {}
            if description := find_xml_value('.//tns:P_7', invoice_line, namespaces=NS):
                line_vals['name'] = description

            if product_id := self._x_ksef_search_product_for_import(invoice_line):
                line_vals['product_id'] = product_id.id

            else:
                message_to_log.append(_("The product '%s' could not be found.", line_vals.get('name')))

            line_vals['quantity'] = float(find_xml_value('.//tns:P_8B', invoice_line, namespaces=NS) or 1)

            if price_unit_untaxed := find_xml_value('.//tns:P_9A', invoice_line, namespaces=NS):
                line_vals['price_unit'] = float(price_unit_untaxed)
                tax_price_included = False

            elif price_unit := find_xml_value('.//tns:P_9B', invoice_line, namespaces=NS):
                tax_price_included = True
                line_vals['price_unit'] = float(price_unit)

            else:
                tax_price_included = False
                message_to_log.append(
                    _("The price unit for the product '%s' could not be found.", line_vals.get('name'))
                )

            if (tax_amount := find_xml_value('.//tns:P_12', invoice_line, namespaces=NS)) and (
                tax_id := self._x_ksef_search_tax_for_import(
                    amount_code=tax_amount,
                    price_included=tax_price_included,
                )
            ):
                line_vals['tax_ids'] = [fields.Command.set(tax_id.ids)]

            else:
                if tax_price_included:
                    message_to_log.append(
                        _(
                            'Could not retrieve the tax: %s %% "Included in Price" for line \'%s\'.',
                            tax_amount,
                            line_vals.get('name', ''),
                        )
                    )

                else:
                    message_to_log.append(
                        _(
                            'Could not retrieve the tax: %s %% not "Included in Price" for line \'%s\'.',
                            tax_amount,
                        )
                    )

            invoice_lines_vals.append(line_vals)

        return invoice_lines_vals

    @staticmethod
    def _x_ksef_get_vendor_move_type(xml_tree):
        return VENDOR_MOVE_TYPE_MAPPING.get(
            find_xml_value('.//tns:RodzajFaktury', xml_tree, namespaces=NS), 'in_invoice'
        )

    @api.model
    def _x_ksef_import_vendor_invoice(self, xml_tree):
        with Form(self) as self:
            message_to_log = []

            self.move_type = self._x_ksef_get_vendor_move_type(xml_tree)

            if partner_vat := find_xml_value(
                './/tns:Podmiot1//tns:DaneIdentyfikacyjne//tns:NIP', xml_tree, namespaces=NS
            ):
                if partner_id := self.env['res.partner'].search(
                    [
                        ('vat', '=ilike', '%' + partner_vat),
                    ],
                    limit=1,
                ):
                    self.partner_id = partner_id

                else:
                    partner_name = find_xml_value(
                        './/tns:Podmiot1//tns:DaneIdentyfikacyjne//tns:Nazwa', xml_tree, namespaces=NS
                    )

                    self.partner_id = self.env['res.partner'].create(
                        {
                            'name': partner_name,
                            'vat': partner_vat,
                        }
                    )

                    message_to_log.extend(
                        (
                            _(
                                'A vendor with a matching Tax ID was not found. '
                                'One with the corresponding details was created.'
                            ),
                            '',
                        )
                    )

            self.journal_id = self.partner_id.x_ksef_purchase_journal_id or self.company_id.x_ksef_purchase_journal_id

            if invoice_date := find_xml_value('.//tns:P_1', xml_tree, namespaces=NS):
                self.pl_vat_date = self.invoice_date = dateutil.parser.parse(invoice_date, ignoretz=True).date()

            if invoice_sale_date := find_xml_value('.//tns:P_6', xml_tree, namespaces=NS):
                self.x_invoice_sale_date = dateutil.parser.parse(invoice_sale_date, ignoretz=True).date()

            if invoice_number := find_xml_value('.//tns:P_2', xml_tree, namespaces=NS):
                self.ref = invoice_number

            if currency_code := find_xml_value('.//tns:KodWaluty', xml_tree, namespaces=NS):
                self.currency_id = self.env['res.currency'].search([('name', '=', currency_code)], limit=1)

            for field_name, field_value in self._x_ksef_parse_annotations(xml_tree).items():
                self[field_name] = field_value

            self.invoice_line_ids = [
                fields.Command.create(vals)
                for vals in self._x_ksef_parse_invoice_lines(xml_tree, self.move_type, message_to_log)
            ]

            message = Markup('<br/>').join(message_to_log)
            self.sudo().message_post(body=message)

        return self

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

    def x_ksef_generate_qr_code_url_pair(self) -> Optional[Tuple[Tuple[str, str], ...]]:
        ksef_edi_document_id = self.edi_document_ids.filtered(lambda doc_id: doc_id.edi_format_id.code == KSEF_CODE)

        if not ksef_edi_document_id.attachment_id:
            return None

        nip = self.company_id.partner_id.x_get_pl_vat(raise_exception=True)

        ksef_url = KsefClient.build_invoice_verification_url(
            base_qr_url=self.company_id.x_ksef_settings_id.qr_code_url,
            nip=nip,
            issue_date=self.invoice_date,
            invoice_xml=ksef_edi_document_id.attachment_id.raw,
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
            for edi_format in move_id.journal_id.edi_format_ids:
                is_edi_needed = move_id.is_invoice(include_receipts=False) and edi_format._is_required_for_invoice(
                    move_id
                )

                if is_edi_needed:
                    if errors := edi_format._check_move_configuration(move_id):
                        raise UserError(_('Invalid invoice configuration:\n%s', '\n'.join(errors)))

                    existing_edi_document = move_id.edi_document_ids.filtered(lambda x: x.edi_format_id == edi_format)
                    if existing_edi_document:
                        existing_edi_document.write(
                            {
                                'state': 'to_send',
                                'attachment_id': False,
                            }
                        )

                    else:
                        edi_document_vals_list.append(
                            {
                                'edi_format_id': edi_format.id,
                                'move_id': move_id.id,
                                'state': 'to_send',
                            }
                        )

        self.env['account.edi.document'].create(edi_document_vals_list)
        self.edi_document_ids._process_documents_no_web_services()

        return self

    def _x_post_wo_validation(self, soft=True):
        posted_ids = super()._x_post_wo_validation(soft=soft)
        self._x_ksef_post_edi()

        return posted_ids

    def _post(self, soft=True):
        if not self.x_get_is_poland():
            # noinspection PyUnusedLocal
            self = self.with_context(skip_account_edi_cron_trigger=True)

        return super()._post(soft=soft)

    def _is_ready_to_be_sent(self):
        if self.env.context.get('skip_account_edi_cron_trigger'):
            return False

        return super()._is_ready_to_be_sent()

    def x_ksef_get_invoice_line_ids(self):
        self.ensure_one()

        invoice_line_ids = self.invoice_line_ids.filtered(lambda l_id: not l_id.display_type)

        if self.advance_invoices_ids:
            invoice_line_ids = invoice_line_ids.filtered(lambda l_id: not l_id._get_downpayment_lines())

        if self.company_id.x_ksef_enable_ignore_zero_amount_lines:
            invoice_line_ids = invoice_line_ids.filtered(
                lambda l_id: not float_is_zero(
                    l_id.price_unit, self.env['decimal.precision'].precision_get('Product Price')
                )
            )

        return invoice_line_ids
