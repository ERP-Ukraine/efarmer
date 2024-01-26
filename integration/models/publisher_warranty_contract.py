# See LICENSE file for full copyright and licensing details.

from odoo import models


class PublisherWarrantyContract(models.AbstractModel):
    _inherit = 'publisher_warranty.contract'
    _description = 'Publisher Warranty Contract'

    def update_notification(self, cron_mode=True):
        """ Override method for checking Ecosystem Subscription """
        res = super(PublisherWarrantyContract, self).update_notification(cron_mode)
        self.env['res.config.settings'].update_ecosystem_subscription_info()
        return res
