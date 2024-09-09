# See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api


class SaleIntegration(models.Model):
    _inherit = 'sale.integration'

    order_name_ref = fields.Char(
        string='Sales Order Prefix',
        help=(
            'Set a unique prefix for orders to easily identify those imported from this '
            'integration. This prefix will precede the order number in Odoo.'
        ),
    )

    _sql_constraints = [
        (
            'order_name_ref_unique',
            'unique(order_name_ref)',
            'Sale Order prefix name should be unique.'
        ),
    ]

    @api.model
    def default_get(self, default_fields):
        # Because fields may not be created when installing
        # We have to override default_get to prefill them
        values = super(SaleIntegration, self).default_get(default_fields)

        values['so_delivery_note_field'] = \
            self.env.ref('integration.field_sale_order__integration_delivery_note').id
        values['picking_delivery_note_field'] = \
            self.env.ref('stock.field_stock_picking__note').id

        return values

    so_external_reference_field = fields.Many2one(
        string='Sales Order External Reference Field',
        comodel_name='ir.model.fields',
        ondelete='cascade',
        help=(
            'Specify a Sales Order field (character or text types only) to record an external '
            'sales order number. This is supplementary to the "External Sales Order Ref" field '
            'and can be used for enhanced order tracking and integration purposes.'
        ),
        required=False,
        domain='[("store", "=", True), '
               '("model_id.model", "=", "sale.order"), '
               '("ttype", "in", ("text", "char")) ]',
    )

    so_delivery_note_field = fields.Many2one(
        string='Sales Order Delivery Note Field',
        comodel_name='ir.model.fields',
        ondelete='cascade',
        help=(
            'Specify the Sales Order field (character or text types only) where the Delivery '
            'Note from the e-commerce system will be recorded. By default, the system uses the '
            'field specified under the e-commerce tab of the Sales Order. However, you can '
            'designate any compatible field, including those from third-party modules.'
        ),
        required=True,
        domain='[("store", "=", True), '
               '("model_id.model", "=", "sale.order"), '
               '("ttype", "in", ("text", "char")) ]',
    )

    picking_delivery_note_field = fields.Many2one(
        string='Stock Picking Delivery Note Field',
        comodel_name='ir.model.fields',
        ondelete='cascade',
        help=(
            'Specify the Stock Picking field (character or text types only) to capture the '
            'Delivery Note from the e-commerce system. The "Note" field on Stock Picking is used '
            'as the standard field, but you have the flexibility to assign any compatible field, '
            'including those from third-party modules.'
        ),
        required=True,
        domain='[("store", "=", True), '
               '("model_id.model", "=", "stock.picking"), '
               '("ttype", "in", ("text", "char")) ]',
    )

    default_sales_team_id = fields.Many2one(
        string='Default Sales Team for Orders',
        comodel_name='crm.team',
        help=(
            'Select a default Sales Team to be automatically assigned to all Sales Orders '
            'imported from the e-Commerce system.'
        ),
        check_company=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]"
    )

    default_sales_person_id = fields.Many2one(
        string='Default Sales Person for Orders',
        comodel_name='res.users',
        help='Select a default Sales Person to be automatically assigned to all new orders.',
        check_company=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]"
    )

    customer_company_vat_field = fields.Many2one(
        string='VAT/Reg. Number Field',
        comodel_name='ir.model.fields',
        ondelete='cascade',
        help=(
            'Identify the field in the Company record (limited to character type fields) to '
            'store the Company\'s VAT/Registration Number from the e-commerce system. While '
            'the default is the VAT field on the Company, you can designate any custom field, '
            'including those from third-party modules.'
        ),
        required=False,
        domain='[("store", "=", True), '
               '("model_id.model", "=", "res.partner"), '
               '("ttype", "=", "char") ]',
    )

    customer_company_vat_field_name = fields.Char(
        related='customer_company_vat_field.name',
    )

    customer_personal_id_field = fields.Many2one(
        string='Personal ID Field',
        comodel_name='ir.model.fields',
        ondelete='cascade',
        help=(
            'Specify the field in the Contact record (limited to character type fields) where '
            'the Personal ID Number from the e-commerce system will be stored. This is '
            'particularly important for localizations that require personal identification, '
            'such as the Italian market.'
        ),
        required=False,
        domain='[("store", "=", True), '
               '("model_id.model", "=", "res.partner"), '
               '("ttype", "=", "char") ]',
    )

    default_customer = fields.Many2one(
        string='Default Customer',
        comodel_name='res.partner',
        help=(
            'Specify a default customer in Odoo for orders that lack customer information in the '
            'E-commerce system. This ensures all orders are associated with a customer record.'
        ),
    )
