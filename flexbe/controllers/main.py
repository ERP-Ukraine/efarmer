import logging
from odoo.http import Controller, Response, request, route
from odoo.exceptions import ValidationError


_logger = logging.getLogger(__name__ + ' [Flexbe]')


class Flexbe(Controller):

    @route('/flexbe/webhook', type='http', auth='none', methods=['POST'], csrf=False)
    def flexbe_webhook(self, **kwargs):
        try:
            domain = kwargs.get('site[domain]')
            is_valid_domain = request.env['flexbe.domain'].is_valid_domain(domain)
            if not is_valid_domain:
                raise ValidationError('Invalid domain.')

            event = kwargs.get('event')
            if event != 'lead':
                raise ValidationError('There is an unexpected event.')

            request.env['crm.lead'].sudo().create_lead_from_flexbe(kwargs)
            return Response('OK', status=200)

        except ValidationError as e:
            _logger.error(e)
            _logger.info(kwargs)
            return Response('Forbidden', status=403)
