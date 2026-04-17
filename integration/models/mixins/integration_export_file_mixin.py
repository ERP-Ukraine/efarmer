# See LICENSE file for full copyright and licensing details.

import subprocess

from odoo import models, fields, _
from odoo.exceptions import ValidationError, UserError


class ExportFileMixin(models.AbstractModel):
    _name = 'export.file.mixin'
    _description = 'Export File Mixin'

    export_html = fields.Html(
        string='Export HTML',
    )
    export_pdf = fields.Binary(
        string='Export PDF',
    )
    export_json = fields.Json(
        string='Export JSON',
    )

    def download_html(self):
        self.ensure_one()
        if not self.export_html:
            raise ValidationError(self._get_empty_export_field_error_message('html'))
        return self._action_download('html')

    def download_pdf(self):
        self.ensure_one()
        if not self.export_pdf:
            raise ValidationError(self._get_empty_export_field_error_message('pdf'))
        return self._action_download('pdf')

    def download_json(self):
        self.ensure_one()
        if not self.export_json:
            raise ValidationError(self._get_empty_export_field_error_message('json'))
        return self._action_download('json')

    def _get_empty_export_field_error_message(self, extension):
        return _(
            'Fill the export_%s field with the %s content to download before calling this method.'
            'Or implement the download_%s method in the model %s.'
        ) % (extension, extension.capitalize(), extension, self._name)

    def _action_download(self, file_format):
        return {
            'type': 'ir.actions.act_url',
            'name': _('Download %s') % file_format.capitalize(),
            'target': 'self',
            'url': '/integration/file/export/%s/%s/%s' % (self._name, self.id, file_format),
        }

    def _convert_html_to_pdf_bytes(self, html_content):
        """
        Convert HTML content to PDF bytes using wkhtmltopdf.

        :param html_content: HTML string to convert
        :return: bytes - PDF content as binary data
        :raises: UserError if PDF generation fails
        """
        if not html_content:
            raise UserError(_('No HTML content provided for PDF conversion'))

        try:
            html_bytes = html_content.encode('utf-8') if isinstance(html_content, str) else html_content

            result = subprocess.run(
                ['wkhtmltopdf', '--quiet', '-', '-'],
                input=html_bytes,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )

            pdf_bytes = result.stdout

            if not pdf_bytes or not pdf_bytes.startswith(b'%PDF'):
                raise UserError(_('Invalid PDF generated. Check HTML content and wkhtmltopdf installation.'))

            return pdf_bytes

        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode('utf-8', errors='ignore') if e.stderr else str(e)
            raise UserError(_('PDF generation failed: %s') % error_msg)
        except FileNotFoundError:
            raise UserError(_('wkhtmltopdf is not installed. Please install it to generate PDFs.'))
        except Exception as e:
            raise UserError(_('Failed to generate PDF: %s') % str(e))
