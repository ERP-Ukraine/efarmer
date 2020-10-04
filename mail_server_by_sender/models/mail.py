# -*- coding: utf-8 -*-

from odoo import api, models, tools


class Message(models.Model):
    _inherit = 'mail.message'

    @api.model_create_multi
    def create(self, values_list):
        # If there is outgoing mail server with username equals to sender's address - use it!
        for values in values_list:
            if 'email_from' not in values:
                values['email_from'] = self._get_default_from()
            if not values.get('mail_server_id'):
                sender_address = tools.email_split(values['email_from'])
                if not sender_address:
                    continue
                server = self.env['ir.mail_server'].sudo().search(
                    [('smtp_user', '=', sender_address[0])], limit=1)
                if not server:
                    continue
                values['mail_server_id'] = server.id
        return super(Message, self).create(values_list)
