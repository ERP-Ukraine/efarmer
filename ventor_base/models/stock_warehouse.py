# Copyright 2020 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import api, models, fields


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    is_internal = fields.Boolean(
        string='Is Internal Warehouse',
    )

    @api.model
    def create(self, vals):
        res = super(StockWarehouse, self).create(vals)
        res.update_users_calculated_warehouse()
        return res

    def update_users_calculated_warehouse(self):
        users = self.env['res.users'].with_context(active_test=False).search([
            ('share', '=', False)])
        wh_ids = self.env['stock.warehouse'].with_context(active_test=False).search([
            ('id', '!=', self.id)]).ids
        wh_ids.sort()
        modified_user_ids = []
        for user in users.with_context(active_test=False):
            # Because of specifics on how Odoo working with companies on first start, we have to filter by company
            user_wh_ids = user.allowed_warehouse_ids.filtered(lambda wh: wh.company_id.id == self.env.company.id).ids
            user_wh_ids.sort()
            if wh_ids == user_wh_ids:
                user.allowed_warehouse_ids = [(4, self.id, 0)]
                modified_user_ids.append(user.id)

        # Because access rights are using this field, we need to invalidate cache
        if modified_user_ids:
            self.env['res.users'].invalidate_cache(['allowed_warehouse_ids'], modified_user_ids)
