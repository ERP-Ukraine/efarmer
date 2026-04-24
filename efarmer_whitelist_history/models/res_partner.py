# -*- coding: utf-8 -*-
import datetime
import requests
import logging
from odoo import fields, models, release, api, _

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def action_check_partner_whitelist(self):
        self.ensure_one()
        if not self.country_id or self.country_id.code.upper() != self.env.ref('base.pl').code.upper():
            self.env['bus.bus']._sendone(self.env.user.partner_id, 'simple_notification', {
                'title': _('Check Contact\'s Country'),
                'message': _('You can check only contacts from Poland'),
                'sticky': False,
                'warning': True,
            })
            return
        elif not self.vat:
            self.env['bus.bus']._sendone(self.env.user.partner_id, 'simple_notification', {
                'title': _('Check Contact\'s VAT'),
                'message': _('Please, fill the VAT field'),
                'sticky': True,
                'warning': True,
            })
            return
        nip = self.vat.upper().replace('PL', '')
        response = requests.get(
            f'https://wl-api.mf.gov.pl/api/search/nip/{nip}',
            params={'date': datetime.date.today().isoformat()},
            headers={'user-agent': f'{release.description} {release.version}'},
        )
        if response.ok:
            result = response.json()
            result = result.get('result', {})
            subject = result.get('subject', None)
            if subject:
                body = (f'Whitelist check. \n Request Date: {result.get("requestDateTime", "")}. Request ID: {result.get("requestId", "")} \n '
                           f'{subject.get("name", "")}, nip: {subject.get("nip", "")}, statusVat: {subject.get("statusVat", "")}')
            else:
                body = (f'Whitelist check. \n Request Date: {result.get("requestDateTime", "")}. Request ID: {result.get("requestId", "")}. \n '
                           f'VAT {self.vat} hasn\'t been found.')
            self.message_post(body=body)

        else:
            result = response.json()
            self.env['bus.bus']._sendone(self.env.user.partner_id, 'simple_notification', {
                'title': _('Error'),
                'message': _(result.get('message')),
                'sticky': True,
                'warning': True,
            })
