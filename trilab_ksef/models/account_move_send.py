from odoo import _, api, models
from odoo.addons.trilab_ksef.models.account_edi_format import KSEF_CODE


class AccountMoveSend(models.AbstractModel):
    _inherit = 'account.move.send'

    @api.model
    def _is_ksef_applicable(self, move) -> bool:
        ksef_format_id = self.env['account.edi.format'].search([('code', '=', KSEF_CODE)], limit=1)
        return bool(ksef_format_id and ksef_format_id._get_move_applicability(move))

    def _get_all_extra_edis(self) -> dict:
        res = super()._get_all_extra_edis()
        res['ksef'] = {
            'label': _('Generate KSeF XML'),
            'is_applicable': self._is_ksef_applicable,
        }
        return res

    def _hook_invoice_document_before_pdf_report_render(self, invoice, invoice_data):
        super()._hook_invoice_document_before_pdf_report_render(invoice, invoice_data)
        if 'ksef' not in (invoice_data.get('extra_edis') or []) or not (
            ksef_format_id := self.env['account.edi.format'].search([('code', '=', KSEF_CODE)], limit=1)
        ):
            return

        if not (xml_content := ksef_format_id._x_ksef_content_edi(invoice)):
            return

        attachment_id = (
            self.env['ir.attachment']
            .sudo()
            .create(
                {
                    'name': 'KSEF_{}.xml'.format(invoice.name.replace('/', '_')),
                    'raw': xml_content,
                    'mimetype': 'application/xml',
                    'res_model': 'account.move',
                    'res_id': invoice.id,
                }
            )
        )

        if edi_doc_id := invoice.edi_document_ids.filtered(lambda d_id: d_id.edi_format_id == ksef_format_id):
            edi_doc_id.attachment_id = attachment_id

        invoice_data['x_ksef_attachment_id'] = attachment_id.id
