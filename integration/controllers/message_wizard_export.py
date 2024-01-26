# See LICENSE file for full copyright and licensing details.

from odoo.http import Controller, route, request, content_disposition


class MessageWizardExport(Controller):

    @route('/integration/messagewizard/export', type='http', auth='user')
    def download_message_wizard_html(self, res_id):
        request.env.cr.execute(
            'SELECT message_html FROM message_wizard WHERE id = %s', (res_id,)
        )
        select = request.env.cr.fetchone()
        html_text = select and select[0] or ''

        headers = [
            ('Content-Type', 'text/html'),
            ('Content-Length', len(html_text)),
            ('Content-Disposition', content_disposition('message-wizard.html')),
        ]

        return request.make_response(html_text, headers=headers)
