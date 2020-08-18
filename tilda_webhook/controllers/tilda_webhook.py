from odoo import http
from ..utils.tilda_request_manager import TildaRequestManager


class TildaWebhook(http.Controller):

    @http.route('/tilda/webhook', type='http', auth='none', methods=['POST'], cors='*', csrf=False)
    def tilda_webhook(self, **kwargs):
        '''Use this route as webhook url to catch all leads and orders.'''
        if kwargs.get('test') != 'test':  # just ping
            TildaRequestManager(kwargs, http.request).run()

        return http.Response('OK', status=200)
