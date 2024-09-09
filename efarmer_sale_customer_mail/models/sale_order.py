# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import models, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def write(self, values):
        res = super().write(values)
        if values.get('state') and values.get('state') == 'to_confirm':
            for order in self:
                if any(product.detailed_type in ['consu', 'product'] for product in order.order_line.mapped("product_id")):
                    order.check_customer_portal_access()
                    product_codes = order.order_line.mapped("product_id").filtered(lambda p: p.default_code).mapped("default_code")
                    if any([code.startswith("KDU.0044") for code in product_codes]):
                        template_id = order.env.ref("efarmer_sale_customer_mail.mail_template_sale_payment_confirmation")
                        if template_id:
                            order.message_post_with_template(
                                template_id.id,
                                composition_mode="comment",
                                email_layout_xmlid="mail.mail_notification_light",
                            )
        return res

    def check_customer_portal_access(self):
        related_user_id = self.env["res.users"].search([("partner_id", "=", self.partner_id.id)])
        if not related_user_id:
            action = self.env.ref(
                "portal.partner_wizard_action_create_and_open").with_context(active_ids=[self.partner_id.id]).run()
            user_ids = self.env['portal.wizard'].browse(action.get("res_id", None)).user_ids
            user_ids = user_ids.filtered(lambda u: u.partner_id.id == self.partner_id.id)
            for user in user_ids:
                if user.is_portal:
                    self._send_email_portal_reminder(user)
                else:
                    user.action_grant_access()
        else:
            for user in related_user_id:
                if user.has_group('base.group_portal'):
                    self._send_email_portal_reminder(user)
                else:
                    related_user_id.action_grant_access()

    def _send_email_portal_reminder(self, user_id):
        """ send notification email to a portal user """
        self.ensure_one()
        template = self.env.ref('efarmer_sale_customer_mail.mail_template_data_portal_reminder')
        if not template:
            raise UserError(_('The template "Portal User Reminder" not found for sending email to the portal user.'))
        lang = user_id.sudo().lang
        partner = user_id.sudo().partner_id
        partner.signup_prepare()
        self.with_context(signup_force_type_in_url='', lang=lang).message_post_with_template(
            template.id,
            composition_mode="comment",
            email_layout_xmlid="mail.mail_notification_light",
        )
        return True

