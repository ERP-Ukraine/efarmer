# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import fields, models, api


class AccountFiscalPositionTax(models.Model):
    _inherit = 'account.fiscal.position.tax'

    product_func_id = fields.Many2one(
        comodel_name='product.function',
        string='Product Function',
    )

    product_vat_id = fields.Many2one(
        comodel_name='product.vat',
        string='Product Vat',
    )

    country_id = fields.Many2one(
        comodel_name='res.country',
        string='Country',
    )

    # This field its copy field company_type in res.partner model
    partner_company_type = fields.Selection(
        string='Company Type',
        selection=[
            ('person', 'Individual'),
            ('company', 'Company')
        ],
    )
