# Copyright 2021 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    @api.constrains("lot_id", "inventory_quantity")
    def _check_product_lot(self):
        """ check product lot/serial except for stock_fix_lot """

        for quant in self:
            if (
                    not quant.inventory_quantity
                    or not quant.company_id.force_lot_validation_on_inventory_adjustment
                    or (
                    quant.env.context.get("skip_product_lot_check") and not quant.inventory_quantity)
            ):
                return
            if quant.tracking in ("lot", "serial") and not quant.lot_id:
                raise ValidationError(
                    _(
                        "You need to supply a Lot/Serial number for product: %s",
                        quant.product_id.display_name,
                    )
                )

    @api.model
    def user_has_groups(self, groups):
        # we need to override method as we need different access group
        # to be allowed to validate inventory
        if (
            self.env.context.get("validate_inventory")
            and groups == "stock.group_stock_manager"
        ):
            groups = "ventor_base.merp_user_validate_inventory_adjustment"
        res = super(StockQuant, self).user_has_groups(groups)
        return res

    def _apply_inventory(self):
        res = super(StockQuant, self.with_context(validate_inventory=True))._apply_inventory()
        return res
