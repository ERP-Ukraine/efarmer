import logging
import werkzeug
from odoo import models, http, SUPERUSER_ID

_logger = logging.getLogger(__name__)


class TildaRequestManager:
    """
    Example of use:
        TildaRequestManager(kwargs, odoo.http.request).run()
    """

    def __init__(self, kwargs, request):
        assert isinstance(kwargs, dict)
        assert isinstance(request, werkzeug.LocalProxy)

        self._kwargs = kwargs
        self._request = request

    def run(self):
        referrer = self._request.httprequest.referrer
        tilda_website = self._request.env['tilda.website'].sudo().get_by_referrer(referrer)

        if tilda_website:
            self._create(tilda_website)
        else:
            self._log_error('Cannot found a Tilda website by the referrer.')

    def _create(self, tilda_website):
        model_su = self._request.env['crm.lead'].sudo().with_context(mail_create_nosubscribe=True)

        vals = {'name': self._kwargs.get('tranid') or self._kwargs.get('formid', 'Tilda lead')}
        vals.update(self._get_utm_vals(model_su))
        vals.update(tilda_website.map_tilda_to_odoo_fields(self._kwargs))
        vals.update(model_su.get_creation_vals_for_tilda_webhook(self._kwargs, vals))
        record = model_su.create(vals)

        _logger.info(
            'A new %s record was created with id=%s from Tilda document with id=%s.',
            model_su._name, record.id, self._kwargs.get('tranid'),
        )

    def _get_utm_vals(self, model_su):
        res = {'referred': self._request.httprequest.referrer}

        tracking_fields = self._request.env['utm.mixin'].sudo().tracking_fields()
        for utm_param, field_name, __ in tracking_fields:
            utm_param_value = self._kwargs.get(utm_param, '').strip()
            if utm_param_value:
                res_model_su = getattr(model_su, field_name)

                res_record = res_model_su.search([('name', '=', utm_param_value)], limit=1)
                if res_record:
                    res[field_name] = res_record.id
                else:
                    utm_param_create_vals = {'name': utm_param_value}
                    # utm.campaign is more complicated than just label
                    # and it has the necessary `user_id` field
                    if field_name == 'campaign_id':
                        utm_param_create_vals['user_id'] = SUPERUSER_ID

                    res_record = res_model_su.create(utm_param_create_vals)
                    res[field_name] = res_record.id

        return res

    def _log_error(self, msg='Unexpected error.'):
        _logger.warn('\n'.join((
            msg,
            'referrer: {}'.format(self._request.httprequest.referrer),
            'kwargs: {}'.format(self._kwargs)
        )))
