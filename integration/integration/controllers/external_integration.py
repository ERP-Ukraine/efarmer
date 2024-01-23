#  See LICENSE file for full copyright and licensing details.

import logging
import json

from odoo.http import Controller, route, request
from odoo import SUPERUSER_ID


_logger = logging.getLogger(__name__)

INTEGRATION_API_HEADER = 'Integration-Api-Key'


class ExternalIntegration(Controller):

    @route('/<string:dbname>/integration/<int:integration_id>/external-order/<string:order_id>',
           type='http', methods=['GET'], auth='public')
    def get_pdf_invoice(self, *args, **kw):
        """ Get PDF invoice for the order. """
        _logger.info('ExternalIntegration.get_pdf_invoice()')

        headers = [
            ('Content-Type', 'application/json'),
            ('Cache-Control', 'no-store'),
        ]
        body = {'code': 0, 'message': '', 'data': []}

        request.session.db = kw.get('dbname')
        env = request.env(user=SUPERUSER_ID)

        headers_api_key = request.httprequest.headers.get(INTEGRATION_API_HEADER)
        kwargs_api_key = kw.get('integration_api_key')
        if not headers_api_key and not kwargs_api_key:
            body.update({'code': 1, 'message': 'Integration API key is missing.'})
            return request.make_response(json.dumps(body), headers=headers)

        ResConfig = env['res.config.settings']
        internal_api_key = ResConfig.get_integration_api_key()
        if internal_api_key not in [headers_api_key, kwargs_api_key]:
            body.update({'code': 1, 'message': 'Integration API key is invalid.'})
            return request.make_response(json.dumps(body), headers=headers)

        integration_id = kw.get('integration_id')
        integration = env['sale.integration'].browse(integration_id).exists()
        if not integration or integration.state == 'draft':
            message = f'Integration ID {integration_id} not found/or inactive in Odoo'
            body.update({'code': 1, 'message': message})
            return request.make_response(json.dumps(body), headers=headers)

        order_code = kw.get('order_id')
        order = env['sale.order'].from_external(integration, order_code, False)
        if not order:
            message = f'Odoo order not found from external code {order_code}.'
            body.update({'code': 1, 'message': message})
            return request.make_response(json.dumps(body), headers=headers)

        # Get status code, result message and data with link to PDF invoice
        code, message, data = order._prepare_pdf_invoice()
        body.update({'code': code, 'message': message, 'data': data})

        response = request.make_response(json.dumps(body), headers=headers)

        return response
