# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import pytz

from collections import defaultdict, Counter
from datetime import date, datetime
from dateutil.relativedelta import relativedelta

from odoo import api, exceptions, fields, models, _, Command
from odoo.osv import expression
from odoo.tools import is_html_empty
from odoo.tools.misc import clean_context, get_lang, groupby

_logger = logging.getLogger(__name__)


class MailActivity(models.Model):
    _inherit = 'mail.activity'

    def action_open_document(self):
        """ Opens the related record based on the model and ID """
        self.ensure_one()
        return {
            'res_id': self.res_id,
            'res_model': self.res_model,
            'target': 'current',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
        }
