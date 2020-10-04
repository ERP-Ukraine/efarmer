# -*- coding: utf-8 -*-
# pylint: disable=invalid-commit
import json
import logging
from datetime import datetime

import requests
from odoo import _, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class GoogleCalendar(models.AbstractModel):
    _inherit = 'google.calendar'

    def get_sequence(self, instance_id):
        params = {
            # 'fields': 'sequence',
            'access_token': self.get_token()}
        headers = {'Content-type': 'application/json'}
        url = "/calendar/v3/calendars/%s/events/%s" % ('primary', instance_id)
        dummy, content, dummy = self.env['google.service']._do_request(
            url, params, headers, type='GET')
        # ERPU FIX
        # `content` may be empty string. So we have to check before calling get()
        if isinstance(content, dict):
            user_to_sync = self.ids[0] if self.ids else self.env.uid
            current_user = self.env['res.users'].sudo().browse(user_to_sync)
            organizer = content.get('organizer', {})
            if organizer.get('email', '') == current_user.google_calendar_cal_id:
                return content.get('sequence', 0)
        _logger.debug('Event `%s`. Received data `%s`', instance_id, str(content))
        raise ValidationError(_('Trying to modify unknown or read-only event %s') % instance_id)

    def update_recurrent_event_exclu(self, instance_id, event_ori_google_id, event_new):
        """ Update event on google calendar
            :param instance_id : new google cal identifier
            :param event_ori_google_id : origin google cal identifier
            :param event_new : record of calendar.event to modify
        """
        data = self.generate_data(event_new)
        url = "/calendar/v3/calendars/%s/events/%s?access_token=%s" % ('primary', instance_id,
                                                                       self.get_token())
        headers = {'Content-type': 'application/json'}

        _originalStartTime = dict()
        if event_new.allday:
            _originalStartTime['date'] = event_new.recurrent_id_date.strftime("%Y-%m-%d")
        else:
            _originalStartTime['dateTime'] = event_new.recurrent_id_date.strftime(
                "%Y-%m-%dT%H:%M:%S.%fz")
        seq = 0
        try:
            seq = self.get_sequence(instance_id)
        except ValidationError as e:
            _logger.debug(e)
            return '2', '', ''
        data.update(
            recurringEventId=event_ori_google_id,
            originalStartTime=_originalStartTime,
            sequence=seq
        )
        data_json = json.dumps(data)
        return self.env['google.service']._do_request(url, data_json, headers, type='PUT')

    def update_to_google(self, oe_event, google_event):
        url = ("/calendar/v3/calendars/%s/events/%s?fields=%s&access_token=%s" %
               ('primary', google_event['id'], 'id,updated', self.get_token()))
        headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
        data = self.generate_data(oe_event)
        data['sequence'] = google_event.get('sequence', 0)
        data_json = json.dumps(data)
        update_date = fields.Datetime.now()
        current_user = oe_event.user_id
        organizer = google_event.get('organizer', {})
        if organizer.get('email', '') == current_user.google_calendar_cal_id:
            try:
                dummy, content, dummy = self.env['google.service']._do_request(
                    url, data_json, headers, type='PATCH')
                update_date = datetime.strptime(content['updated'], "%Y-%m-%dT%H:%M:%S.%fz")
            except requests.HTTPError as e:
                if e.response.status_code != 403:
                    raise e
                _logger.info("Could not update Google event %s", google_event['id'])
        oe_event.write({'oe_update_date': update_date})
        if self.env.context.get('curr_attendee'):
            self.env['calendar.attendee'].browse(self.env.context['curr_attendee']).write(
                {'oe_synchro_date': update_date})
