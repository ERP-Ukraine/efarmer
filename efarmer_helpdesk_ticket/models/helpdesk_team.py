# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HelpdeskTeam(models.Model):
    _inherit = 'helpdesk.team'

    use_short_form = fields.Boolean(string='Short Form')
    allowed_ticket_type_ids = fields.Many2many(comodel_name='helpdesk.ticket.type', string='Allowed Types')

    @api.onchange('use_product_repairs', 'use_product_returns', 'use_credit_notes')
    def _onchange_use_short_form(self):
        if not self.use_product_repairs and not self.use_product_returns and not self.use_credit_notes:
            self.use_short_form = False


