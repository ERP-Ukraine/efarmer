import base64

from lxml import etree

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import file_path

from ..models.account_move import KSEF_CODE, NS
from ..models.utils import find_xml_value

INVOICE_TYPES = {
    'VAT': 'Faktura podstawowa',
    'KOR': 'Faktura korygująca',
    'ZAL': 'Faktura zaliczkowa',
    'ROZ': 'Faktura wystawiona w związku z art. 106f ust. 3 ustawy',
    'UPR': 'Faktura, o której mowa w art. 106e ust. 5 pkt 3 ustawy',
    'KOR_ZAL': 'Faktura korygująca fakturę zaliczkową',
    'KOR_ROZ': 'Faktura korygująca fakturę wystawioną w związku z art. 106f ust. 3 ustawy',
}


class ReportTrilabKsefInvoice(models.Model):
    _name = 'report.trilab_ksef.report_invoice'
    _description = 'KSeF report invoice'

    # noinspection PyUnusedLocal
    @api.model
    def _get_report_values(self, docids, data=None):
        move_ids = self.env['account.move'].browse(docids)
        data = {}
        xslt = etree.XSLT(etree.parse(file_path('trilab_ksef/data/ksef-invoice.xsl')))

        for move_id in move_ids.sudo().filtered(
            lambda m_id: m_id.x_ksef_attachment_file or m_id.edi_document_ids.attachment_id
        ):
            data.setdefault(move_id.id, {})

            if file_data := (
                move_id.x_ksef_attachment_file
                or fields.first(
                    move_id.edi_document_ids.filtered(lambda d_id: d_id.edi_format_id.code == KSEF_CODE)
                ).attachment_id.datas
            ):
                try:
                    tree = etree.fromstring(base64.b64decode(file_data))

                    data[move_id.id]['number'] = find_xml_value('tns:Fa/tns:P_2', tree, namespaces=NS)
                    data[move_id.id]['type'] = INVOICE_TYPES.get(
                        find_xml_value('tns:Fa/tns:RodzajFaktury', tree, namespaces=NS)
                    )
                    data[move_id.id]['system_info'] = find_xml_value('tns:Naglowek/tns:SystemInfo', tree, namespaces=NS)
                    data[move_id.id]['html'] = xslt(tree)

                except (etree.XMLSyntaxError, etree.XSLTParseError) as error:
                    raise ValidationError(
                        _('Error while parse invoice %s file: %s', move_id.display_name, str(error))
                    ) from error

        return {'doc_ids': docids, 'doc_model': 'account.move', 'docs': move_ids, 'data': data}
