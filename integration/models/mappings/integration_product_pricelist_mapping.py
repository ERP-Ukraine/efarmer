# See LICENSE file for full copyright and licensing details.

from odoo import fields, models, _


class IntegrationProductPricelistMapping(models.Model):
    _name = 'integration.product.pricelist.mapping'
    _inherit = 'integration.mapping.mixin'
    _description = 'Integration Product Pricelist Mapping'
    _mapping_fields = ('pricelist_id', 'external_pricelist_id')

    pricelist_id = fields.Many2one(
        comodel_name='product.pricelist',
        string='Odoo Pricelist',
        ondelete='cascade',
    )
    external_pricelist_id = fields.Many2one(
        comodel_name='integration.product.pricelist.external',
        string='External Pricelist',
        ondelete='cascade',
        required=True,
    )

    def import_special_prices_mapping(self):
        self.ensure_one()
        external = self.external_pricelist_id
        job_kwargs = external._job_kwargs_import_special_prices(self.pricelist_id)
        job = external.with_delay(**job_kwargs).import_special_prices_external()
        external.job_log(job)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('%s: Import Special Prices') % external.name,
                'message': '%s: Queue Jobs "Import Special Prices" were created' % external.name,
                'type': 'success',
                'sticky': False,
            },
        }

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
        odoo_pricelist = pricelist_id.search(domain, limit=1)

        if odoo_pricelist:
            self.pricelist_id = odoo_pricelist.id

        return odoo_pricelist
