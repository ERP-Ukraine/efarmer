# See LICENSE file for full copyright and licensing details.

import base64
import binascii

from odoo import _
from odoo.http import Controller, route, request, content_disposition


class ExportFile(Controller):

    file_type_map = {
        'html': {
            'content_type': 'text/html',
            'mixin_field': 'export_html',
            'needs_decode': False,
        },
        'pdf': {
            'content_type': 'application/pdf',
            'mixin_field': 'export_pdf',
            'needs_decode': True,
        },
        'json': {
            'content_type': 'application/json',
            'mixin_field': 'export_json',
            'needs_decode': False,
        },
    }

    @route('/integration/file/export/<string:model_name>/<int:res_id>/<string:extension>', type='http', auth='user')
    def export_file(self, model_name, res_id, extension):
        record = request.env[model_name].browse(res_id)
        if not record.exists():
            return request.not_found(_(
                'Object with ID "%s" and model "%s" not found.'
            ) % (res_id, model_name))

        if extension not in self.file_type_map:
            return request.not_found(_(
                'File extension "%s" not supported. Supported extensions: %s\n'
                'Update ExportFile controller and ExportFileMixin model.'
            ) % (extension, ", ".join(self.file_type_map.keys())))

        file_config = self.file_type_map[extension]
        file_content = getattr(record, file_config['mixin_field']) or ''

        if not file_content:
            return request.not_found(_('No %s content available for this record.') % extension)

        if file_config.get('needs_decode') and isinstance(file_content, str):
            try:
                file_content = base64.b64decode(file_content)
            except (binascii.Error, ValueError, TypeError) as e:
                return request.not_found(_('Invalid export %s data: %s') % (extension, str(e)))

        content_length = len(file_content)

        return request.make_response(file_content, headers=[
            ('Content-Type', file_config['content_type']),
            ('Content-Length', str(content_length)),
            ('Content-Disposition', content_disposition('%s-%s.%s' % (model_name, res_id, extension))),
        ])
