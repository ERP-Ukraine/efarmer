# Copyright 2020 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import api, models, fields


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    is_internal = fields.Boolean(
        string='Is Internal Warehouse',
    )

    @api.model_create_multi
    def create(self, vals_list):
        res = super(StockWarehouse, self).create(vals_list)
        if res:
            res.update_users_calculated_warehouse()
        return res

    def update_users_calculated_warehouse(self):
        for warehouse in self:
            users = self.env['res.users'].with_context(active_test=False).search([
                ('share', '=', False)])
            wh_ids = self.env['stock.warehouse'].with_context(active_test=False).search([
                ('id', '!=', warehouse.id)]).ids
            wh_ids.sort()
            modified_user_ids = []
            for user in users.with_context(active_test=False):
                # Because of specifics on how Odoo working with companies on first start, we have to filter by company
                user_wh_ids = user.allowed_warehouse_ids.filtered(
                    lambda wh: wh.company_id.id == warehouse.env.company.id
                ).ids
                user_wh_ids.sort()
                if wh_ids == user_wh_ids:
                    user.allowed_warehouse_ids = [(4, warehouse.id, 0)]
                    modified_user_ids.append(user.id)

            # Because access rights are using this field, we need to invalidate cache
            if modified_user_ids:
                self.env['res.users'].browse(modified_user_ids).invalidate_recordset(
                    [
                        'allowed_warehouse_ids',
                    ]
                )
