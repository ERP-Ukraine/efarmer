# -*- coding: utf-8 -*-

from odoo import api, models
from odoo.addons.base.models.ir_mail_server import extract_rfc2822_addresses


class IrMailServer(models.Model):
    _inherit = 'ir.mail_server'

    @api.model
    def send_email(self, message, mail_server_id=None, smtp_server=None, smtp_port=None,
                   smtp_user=None, smtp_password=None, smtp_encryption=None,
                   smtp_ssl_certificate=None, smtp_ssl_private_key=None,
                   smtp_debug=False, smtp_session=None):
        if not mail_server_id:
            # If there is outgoing mail server with username equals to sender's address - use it!
            smtp_from = (message['Return-Path'] or self._get_default_bounce_address() or
                         message['From'])
            sender_address = extract_rfc2822_addresses(smtp_from)[:0]
            if sender_address:
                mail_server_id = self.sudo().search([('smtp_user', '=', sender_address)], limit=1)
        return super().send_email(message, mail_server_id=mail_server_id, smtp_server=smtp_server, smtp_port=smtp_port,
                   smtp_user=smtp_user, smtp_password=smtp_password, smtp_encryption=smtp_encryption,
                   smtp_ssl_certificate=smtp_ssl_certificate, smtp_ssl_private_key=smtp_ssl_private_key,
                   smtp_debug=smtp_debug, smtp_session=smtp_session)
