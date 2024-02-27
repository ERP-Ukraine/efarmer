# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HelpdeskTeam(models.Model):
    _inherit = 'helpdesk.team'

    use_short_form = fields.Boolean(string="Short Form")
