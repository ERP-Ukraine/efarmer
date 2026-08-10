# See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class IntegrationProductPricelistMapping(models.Model):
    _name = 'integration.product.pricelist.mapping'
    _inherit = 'integration.mapping.mixin'
    _description = 'Integration Product Pricelist Mapping'
    _mapping_fields = ('pricelist_id', 'external_pricelist_id')
    _mapping_label = 'Pricelist'

    pricelist_id = fields.Many2one(
        string='Odoo Pricelist',
        comodel_name='product.pricelist',
        ondelete='set null',
    )
    external_pricelist_id = fields.Many2one(
        string='External Pricelist',
        comodel_name='integration.product.pricelist.external',
        ondelete='cascade',
        required=True,
    )

    def _fix_unmapped_pricelist_one(self, external_data=None):
        self.ensure_one()
        self._fix_unmapped_by_search(external_data=external_data)
        return self.pricelist_id

    def _create_pricelist_from_external(self, external_data):  # Currently not used
        pricelist_id = self.pricelist_id
        if pricelist_id or not self.external_pricelist_id:
            return pricelist_id

        if not external_data:
            return pricelist_id

        pricelist_vals = {
            'name': self.external_pricelist_id.name,
            'company_id': self.integration_id.company_id.id,
        }
        odoo_pricelist = pricelist_id.create(pricelist_vals)
        self.pricelist_id = odoo_pricelist.id

        return odoo_pricelist

    def _fix_unmapped_by_search(self, external_data=None):
        pricelist_id = self.pricelist_id
        if pricelist_id or not self.external_pricelist_id:
            return pricelist_id

        domain = [
            ('name', '=ilike', self.external_pricelist_id.name),
            ('company_id', '=', self.integration_id.company_id.id),
        ]
        # Bind the integration language so the translatable product.pricelist name is matched against the
        # translation it was stored under at import time; otherwise the search uses the runtime user's language
        # and silently misses matches in multi-language setups. Falls back to the current context language when
        # the integration language is not configured yet.
        lang_context = self.integration_id.get_integration_lang_context()
        odoo_pricelist = pricelist_id.with_context(**lang_context).search(domain, limit=1)

        if odoo_pricelist:
            self.pricelist_id = odoo_pricelist.id

        return odoo_pricelist
