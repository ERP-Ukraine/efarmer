# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    use_short_form = fields.Boolean(related='team_id.use_short_form', string="Short Form", store=True)


    def action_short_form(self):
        pass


