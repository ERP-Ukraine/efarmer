# See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class IntegrationAccountTaxGroupExternal(models.Model):
    _name = 'integration.account.tax.group.external'
    _inherit = 'integration.external.mixin'
    _description = 'Integration Account Tax Group External'
    _order = 'sequence, id'
    _odoo_model = 'account.tax.group'

    sequence = fields.Integer(
        string='Priority',
        default=10,
        readonly=True,
    )

    external_tax_ids = fields.Many2many(
        comodel_name='integration.account.tax.external',
        relation='external_tax_group_to_external_tax_relation',
        column1='external_tax_group_id',
        column2='external_tax_id',
        string='Related External Taxes',
        readonly=True,
    )

    default_external_tax_id = fields.Many2one(
        comodel_name='integration.account.tax.external',
        string='Default External Tax',
    )

    def try_map_by_external_reference(self, odoo_search_domain=False):
        self.ensure_one()

        # If we found existing mapping, we do not need to do anything
        if self.odoo_record:
            return

        self.create_or_update_mapping()
