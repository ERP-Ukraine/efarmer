# -*- coding: utf-8 -*-
from odoo.addons.sale.controllers import portal


class CustomerPortal(portal.CustomerPortal):

    def _prepare_quotations_domain(self, partner):
        domain = [
            ('message_partner_ids', 'child_of', [partner.commercial_partner_id.id]),
            ('state', 'in', ['sent', 'cancel', 'to_payment', 'to_confirm'])
        ]
        return domain
