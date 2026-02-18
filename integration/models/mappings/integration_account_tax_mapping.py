# See LICENSE file for full copyright and licensing details.

from odoo.tools.sql import escape_psql
from odoo import fields, models


class IntegrationAccountTaxMapping(models.Model):
    _name = 'integration.account.tax.mapping'
    _inherit = 'integration.mapping.mixin'
    _description = 'Integration Account Tax Mapping'
    _mapping_fields = ('tax_id', 'external_tax_id')

    tax_id = fields.Many2one(
        string='Odoo Tax',
        comodel_name='account.tax',
        ondelete='cascade',
        domain="[('type_tax_use','=','sale'), ('company_id', '=', company_id)]",
    )
    external_tax_id = fields.Many2one(
        string='External Tax',
        comodel_name='integration.account.tax.external',
        required=True,
        ondelete='cascade',
    )

    # TODO: remove in Odoo 16 as Deprecated
    external_tax_group_id = fields.Many2one(
        string='External Tax Group',
        comodel_name='integration.account.tax.group.external',
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

        if integration.default_tax_scope:
            tax_vals['tax_scope'] = integration.default_tax_scope
        if integration.default_tax_group_id:
            tax_vals['tax_group_id'] = integration.default_tax_group_id.id

        if external_data.get('price_include'):
            price_include_value = external_data['price_include']
        else:
            price_include_value = self.integration_id.price_including_taxes

        if price_include_value:
            tax_vals['price_include_override'] = 'tax_included'
        else:
            tax_vals['price_include_override'] = 'tax_excluded'
        odoo_tax = tax_id.create(tax_vals)

        account = integration.default_account_id
        if account:
            for line in odoo_tax.invoice_repartition_line_ids | odoo_tax.refund_repartition_line_ids:
                if line.repartition_type == 'tax':
                    line.account_id = account

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
        ]
        if external_data:
            domain.append(
                ('amount', '=', float(external_data['rate']))
            )

            if external_data.get('price_include'):
                price_include_value = external_data['price_include']
            else:
                price_include_value = self.integration_id.price_including_taxes

            if price_include_value:
                value = 'tax_included'
            else:
                value = 'tax_excluded'
            domain.append(
                ('price_include_override', '=', value)
            )

        odoo_tax = tax_id.search(domain, limit=1)
        if odoo_tax:
            self.tax_id = odoo_tax.id

        return odoo_tax
