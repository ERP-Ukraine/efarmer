# See LICENSE file for full copyright and licensing details.

from odoo.tools.sql import escape_psql
from odoo import fields, models


class IntegrationAccountTaxMapping(models.Model):
    _name = 'integration.account.tax.mapping'
    _inherit = 'integration.mapping.mixin'
    _description = 'Integration Account Tax Mapping'
    _mapping_fields = ('tax_id', 'external_tax_id')

    tax_id = fields.Many2one(
        comodel_name='account.tax',
        string='Odoo Tax',
        ondelete='cascade',
        domain="[('type_tax_use','=','sale'), ('company_id', '=', company_id)]",
    )
    external_tax_id = fields.Many2one(
        comodel_name='integration.account.tax.external',
        string='External Tax',
        required=True,
        ondelete='cascade',
    )

    # TODO: remove in Odoo 16 as Deprecated
    external_tax_group_id = fields.Many2one(
        comodel_name='integration.account.tax.group.external',
        string='External Tax Group',
    )

    # TODO: add constain

    def action_import_taxes_from_mapping(self):
        tax_external_ids = self.filtered(lambda x: not x.tax_id).mapped('external_tax_id')
        return tax_external_ids.action_import_taxes_from_external()

    def _fix_unmapped_tax_one(self, external_data=None):
        self.ensure_one()
        self._fix_unmapped_by_search(external_data=external_data)

        tax_id = self.tax_id
        if tax_id or not self.external_tax_id:
            return tax_id

        integration = self.integration_id
        if not self.env.context.get('force_create_tax'):
            if not integration.auto_create_taxes_on_so:
                return False

        if not external_data:
            return tax_id

        tax_vals = {
            'type_tax_use': 'sale',
            'amount_type': 'percent',
            'name': self.external_tax_id.name,
            'amount': float(external_data['rate']),
            'description': f'{external_data["rate"]}%',
            'integration_id': integration.id,
            'company_id': integration.company_id.id,
        }
        if external_data.get('price_include'):
            value = external_data['price_include']
        else:
            value = self.integration_id.price_including_taxes

        tax_vals['price_include'] = value
        odoo_tax = tax_id.create(tax_vals)
        self.tax_id = odoo_tax.id

        return odoo_tax

    def _fix_unmapped_by_search(self, external_data=None):
        tax_id = self.tax_id
        if tax_id or not self.external_tax_id:
            return tax_id

        domain = [
            ('type_tax_use', '=', 'sale'),
            ('amount_type', '=', 'percent'),
            ('name', '=ilike', escape_psql(self.external_tax_id.name)),
            ('company_id', '=', self.integration_id.company_id.id),
            ('integration_id', 'in', [self.integration_id.id, False]),
        ]
        if external_data:
            domain.append(
                ('amount', '=', float(external_data['rate']))
            )

            if external_data.get('price_include'):
                value = external_data['price_include']
            else:
                value = self.integration_id.price_including_taxes
            domain.append(
                ('price_include', '=', value)
            )

        odoo_tax = tax_id.search(domain, limit=1)
        if odoo_tax:
            self.tax_id = odoo_tax.id

        return odoo_tax
