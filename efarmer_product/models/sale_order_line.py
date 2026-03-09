# Copyright 2026 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import _, api, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    @api.model
    def _create(self, data_list):
        for data in data_list:
            if (
                data.get("stored")
                and data["stored"].get("display_type", False)
                and data["stored"].get("tax_id", False)
            ):
                data["stored"]["tax_id"] = []

        return super()._create(data_list)

    # OVERRIDE METHOD
    # def _compute_tax_id(self):
    #     for line in self:
    #         line = line.with_company(line.company_id)
    #         fpos = (
    #             line.order_id.fiscal_position_id
    #             or line.order_id.fiscal_position_id.get_fiscal_position(
    #                 line.order_partner_id.id
    #             )
    #         )
    #         # This filter need for search goods products in SO and set all taxes like a goods product
    #         # Task EF-182-change-doc-layout
    #         default_product_func_id = (
    #             self.env["ir.config_parameter"]
    #             .sudo()
    #             .get_param("product_function.product_function_id")
    #         )
    #         goods_product_lines = line.order_id.order_line.filtered(
    #             lambda x: x.product_id.product_func_id.id
    #             == int(default_product_func_id)
    #         )
    #         if goods_product_lines:
    #             # If company_id is set, always filter taxes by the company
    #             taxes = goods_product_lines[0].product_id.taxes_id.filtered(
    #                 lambda t: t.company_id == line.env.company
    #             )
    #             line.tax_id = fpos.map_tax(taxes, goods_product_lines)
    #         else:
    #             # If company_id is set, always filter taxes by the company
    #             taxes = line.product_id.taxes_id.filtered(
    #                 lambda t: t.company_id == line.env.company
    #             )
    #             line.tax_id = fpos.map_tax(taxes, line)

    def create(self, vals_list):
        lines = super().create(vals_list)
        for line in lines:
            if line.product_id and line.order_id.state in [
                "draft",
                "sale",
                "to_payment",
                "to_confirm",
            ]:
                msg = _("Create line %s", line.product_id.display_name)
                line.order_id.message_post(body=msg)
        return lines

    def unlink(self):
        for line in self:
            if line.product_id and line.order_id.state in [
                "draft",
                "sale",
                "to_payment",
                "to_confirm",
            ]:
                msg = _("Removed line %s", line.product_id.display_name)
                line.order_id.message_post(body=msg)
        return super().unlink()

    def write(self, values):
        specific_lines = self.env["sale.order.line"]
        if values.get("tax_id", []):
            if "display_type" in values and values["display_type"]:
                values["tax_id"] = [fields.Command.clear()]
            else:
                specific_lines = self.filtered(lambda r: r.display_type)

        if "product_uom_qty" in values:
            for line in self:
                if line.product_id and line.order_id.state in [
                    "draft",
                    "sale",
                    "to_payment",
                    "to_confirm",
                ]:
                    msg = _(
                        "Update line {name}. Changed quantity from {old_qty} to {new_qty}".format(
                            name=line.product_id.display_name,
                            old_qty=line.product_uom_qty,
                            new_qty=float(values.get("product_uom_qty")),
                        )
                    )
                    line.order_id.message_post(body=msg)
        if "product_id" in values:
            for line in self:
                if line.product_id and line.order_id.state in [
                    "draft",
                    "sale",
                    "to_payment",
                    "to_confirm",
                ]:
                    msg = _(
                        "The product on the line was changed from {old_product} to {new_product}".format(
                            old_product=line.product_id.display_name,
                            new_product=self.env["product.product"]
                            .browse((values.get("product_id")))
                            .display_name,
                        )
                    )
                    line.order_id.message_post(body=msg)

        if specific_lines:
            return all(
                [
                    super(SaleOrderLine, specific_lines).write(
                        {**values, "tax_id": [fields.Command.clear()]}
                    ),
                    super(SaleOrderLine, self - specific_lines).write(values),
                ]
            )
        else:
            return super(SaleOrderLine, self).write(values)
