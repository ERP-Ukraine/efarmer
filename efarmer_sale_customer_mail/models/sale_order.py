# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def write(self, values):
        res = super().write(values)
        if values.get('state') and values.get('state') == 'to_confirm':
            for order in self:
                product_codes = order.order_line.mapped("product_id").mapped("default_code")
                if any([code.startswith("KDU.0044") for code in product_codes]):
                    order.check_customer_portal_access()
                    template_id = order.env.ref("efarmer_sale_customer_mail.mail_template_sale_payment_confirmation").id
                    if template_id:
                        order.with_context(force_send=True).message_post_with_template(template_id,
                                                                                       composition_mode='comment',
                                                                                   email_layout_xmlid="mail.mail_notification_light")
        return res

    def check_customer_portal_access(self):
        related_user_id = self.env["res.users"].search([("partner_id", "=", self.partner_id.id)])
        if not related_user_id:
            action = self.env.ref(
                "portal.partner_wizard_action_create_and_open").with_context(active_ids=[self.partner_id.id]).run()
            user_ids = self.env['portal.wizard'].browse(action.get("res_id", None)).user_ids
            user_ids = user_ids.filtered(lambda u: u.partner_id.id == self.partner_id.id)
            for user in user_ids:
                user.action_grant_access()
