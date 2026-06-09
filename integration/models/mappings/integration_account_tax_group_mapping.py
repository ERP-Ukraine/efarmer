# See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class IntegrationAccountTaxGroupMapping(models.Model):
    _name = 'integration.account.tax.group.mapping'
    _inherit = 'integration.mapping.mixin'
    _description = 'Integration Account Tax Group Mapping'
    _mapping_fields = ('tax_group_id', 'external_tax_group_id')
    _mapping_label = 'Tax Group'

    tax_group_id = fields.Many2one(  # TODO: deprecated, hide on the form.
        string='Odoo Tax Group',
        comodel_name='account.tax.group',
        ondelete='cascade',
    )

    external_tax_group_id = fields.Many2one(
        string='External Tax Group',
        comodel_name='integration.account.tax.group.external',
        required=True,
        ondelete='cascade',
    )

    # TODO: Remove in Odoo 16 as deprecated
    external_tax_id = fields.Many2one(
        string='Default External Tax',
        comodel_name='integration.account.tax.external',
    )
