# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, _


class IntegrationPricelistWizard(models.TransientModel):
    _name = 'integration.pricelist.wizard'
    _description = 'Integration Pricelist Wizard'

    integration_id = fields.Many2one(
        comodel_name='sale.integration',
        string='Integration',
        default=lambda self: self.integration_ctx_id,
        required=True,
    )
    pricelist_mapping_ids = fields.Many2many(
        comodel_name='integration.product.pricelist.mapping',
        relation='integration_pricelist_wizard_rel',
        column1='wizard_id',
        column2='pricelist_mapping_id',
        string='Pricelist Mappings',
        default=lambda self: self._get_mapping_ids(),
    )

    @property
    def integration_ctx_id(self):
        return self._context.get('active_id')

    def run_import_special_prices(self):
        mappings = self.pricelist_mapping_ids.filtered(lambda x: x.pricelist_id)

        for record in mappings:
            record.import_special_prices_mapping()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Import Special Prices'),
                'message': 'Queue Jobs "Import Special Prices" were created',
                'type': 'success',
                'sticky': False,
            },
        }

    def fetch_pricelist_from_external(self):
        self.integration_id.integrationApiImportPricelists()

        self = self.with_context(active_id=self.integration_id.id)
        self.pricelist_mapping_ids = [(6, 0, self._get_mapping_ids())]

        ir_action = self.env.ref('integration.integration_pricelist_wizard_action')
        action = ir_action.read()[0]
        action['res_id'] = self.id
        return action

    def _get_mapping_ids(self):
        mappings = self.env['integration.product.pricelist.mapping'].search([
            ('integration_id', '=', self.integration_ctx_id),
        ])
        return mappings.ids
