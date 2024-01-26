# See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class IntegrationAccountTaxGroupMapping(models.Model):
    _name = 'integration.account.tax.group.mapping'
    _inherit = 'integration.mapping.mixin'
    _description = 'Integration Account Tax Group Mapping'
    _mapping_fields = ('tax_group_id', 'external_tax_group_id')

    tax_group_id = fields.Many2one(  # TODO: deprecated, hide on the form.
        comodel_name='account.tax.group',
        ondelete='cascade',
    )

    external_tax_group_id = fields.Many2one(
        comodel_name='integration.account.tax.group.external',
        required=True,
        ondelete='cascade',
    )

    # TODO: Remove in Odoo 16 as deprecated
    external_tax_id = fields.Many2one(
        comodel_name='integration.account.tax.external',
        string='Default External Tax',
    )
