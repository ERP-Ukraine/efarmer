import re
import logging
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ServerActions(models.Model):
    _name = 'ir.actions.server'
    _inherit = ['ir.actions.server']

    activity_record = fields.Char(
        string='Activity Record',
        default='[]',
        help='You should set the one tuple and only the first element is important.',
    )

    # [OVERRIDDEN]
    @api.model
    def run_action_next_activity(self, action, eval_context=None):
        if not action.activity_type_id or not self._context.get('active_id') or self._is_recompute(action):
            return False

        records = self.env[action.model_name].browse(self._context.get('active_ids', self._context.get('active_id')))

        # [CHANGE] check activity_record field to be able to set an activity for another model
        activity_record = action.activity_record and action.activity_record.strip()
        if activity_record and activity_record != '[]':
            try:
                found = re.search('\[\["(.+?)"', activity_record)
                if found:
                    records = records.mapped(found.group(1))
            except KeyError:
                _logger.warn('Invalid `activity record` field for the action %s', action.name or action.id)

        vals = {
            'summary': action.activity_summary or '',
            'note': action.activity_note or '',
            'activity_type_id': action.activity_type_id.id,
        }
        if action.activity_date_deadline_range > 0:
            vals['date_deadline'] = fields.Date.context_today(action) + relativedelta(**{action.activity_date_deadline_range_type: action.activity_date_deadline_range})
        for record in records:
            if action.activity_user_type == 'specific':
                user = action.activity_user_id
            elif action.activity_user_type == 'generic' and action.activity_user_field_name in record:
                user = record[action.activity_user_field_name]
            if user:
                vals['user_id'] = user.id
            record.activity_schedule(**vals)
        return False
