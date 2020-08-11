import hashlib
import logging
from urllib.parse import urlparse, unquote, parse_qs

from odoo.addons.base.models.assetsbundle import rjsmin
from odoo.http import STATIC_CACHE, Controller, Response, request, route

_logger = logging.getLogger(__name__)


class Main(Controller):

    @route('/extwebsite/lead', type='http', auth='none',
           methods=['POST'], cors='*', csrf=False)
    def create_lead(self, **kwargs):
        '''Send here the request data for the origin server to create a new lead.'''
        referrer = kwargs.get('referrer')

        if not referrer:
            referrer = request.httprequest and request.httprequest.referrer

        kw_query = {}
        if referrer:
            url = urlparse(unquote(referrer))
            kw_query = parse_qs(url.query)
            referrer = url.netloc + url.path
        else:
            _logger.error('No referrer. Kwargs: %s', kwargs)

        form_uid = kwargs.get('form_id')
        if not form_uid:
            _logger.error('No form id. Kwargs: %s', kwargs)

        if referrer and form_uid:
            model_su = request.env['external.website.form'].sudo()
            domain = [('referrer', '=', referrer), ('form_uid', '=', form_uid)]
            form = model_su.search(domain, limit=1)
            if form:
                # request.httprequest.form is an ImmutableOrderedMultiDict object
                # which allows to get a list of values with the same key.
                #
                # Example form data: 'mark=1&mark=2'
                # `kwargs` will contain `{'mark': '1'}`
                # `request.httprequest.form.getlist('mark')` returns `['1', '2']`
                lead = form.create_lead(request.httprequest.form, kw_query)
                _logger.debug('A new lead was created with id=%s.', lead.id)
            else:
                _logger.error('No form record. Referrer: %s. Kwargs: %s', referrer, kwargs)

        return Response('OK', status=200)

    @route('/extwebsite/client.js', type='http', auth='public')
    def loader(self, *args, **kwargs):
        """Server minified script which will post form data."""
        values = {'base_url': request.env['ir.config_parameter'].sudo().get_param('web.base.url')}
        js_code = request.env.ref('efarm_external_website_leads.script_extform').render(values)
        js_min = rjsmin(js_code.decode())
        checksum = hashlib.sha1(js_min.encode('utf-8')).hexdigest()
        jshttpheaders = [('Content-Type', 'application/javascript; charset=utf-8'),
                         ('Cache-Control', 'public, max-age=%s' % STATIC_CACHE),
                         ('ETag', checksum),
                         ('Content-Length', len(js_min))]
        return request.make_response(js_min, headers=jshttpheaders)
