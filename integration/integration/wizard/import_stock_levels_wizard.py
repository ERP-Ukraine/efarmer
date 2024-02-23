# See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _


class ImportStockLevelsWizard(models.TransientModel):
    _name = 'import.stock.levels.wizard'
    _description = 'Import Stock Levels Wizard'

    integration_id = fields.Many2one(
        comodel_name='sale.integration',
        string='Sale Integration',
        default=lambda self: self._context.get('active_id'),
        required=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        related='integration_id.company_id',
    )
    wizard_line_ids = fields.One2many(
        comodel_name='import.stock.levels.wizard.line',
        inverse_name='wizard_id',
        string='Stock Wizard Lines',
        required=True,
    )
    allow_import = fields.Boolean(
        compute='_compute_allow_import',
        string='Allow Import'
    )

    @api.depends('wizard_line_ids')
    def _compute_allow_import(self):
        for rec in self:
            rec.allow_import = bool(self.wizard_line_ids)

    def _get_stock_level_wizard_lines(self):
        if self.integration_id.advanced_inventory():
            return self.wizard_line_ids
        return self.wizard_line_ids[:1]  # Get the only one record if it's not the Shopify/Magento

    def get_location_lines(self, integration):
        location_line_ids = integration.location_line_ids  # external.stock.location.line
        StockLocationLine = location_line_ids.browse()
        lines_for_import = StockLocationLine.browse()

        wizard_line_ids = self._get_stock_level_wizard_lines()

        for rec in wizard_line_ids:  # import.stock.levels.wizard.line
            wizard_loc_id = rec.location_id  # stock.location
            wizard_external_loc_id = rec.external_location_id  # integration.stock.location.external

            line = location_line_ids.filtered(lambda x: x.erp_location_id == wizard_loc_id)
            if not line:
                vals = dict(
                    integration_id=integration.id,
                    erp_location_id=wizard_loc_id.id,
                    external_location_id=wizard_external_loc_id.id,
                )
                line = StockLocationLine.create(vals)
            else:
                line.external_location_id = wizard_external_loc_id.id

            lines_for_import |= line

        return lines_for_import

    def run_import_stock_levels(self):
        integration = self.integration_id
        location_lines = self.get_location_lines(integration)

        for idx, line in enumerate(location_lines, start=1):
            job_kwargs = integration._job_kwargs_import_stock_from_location(line, block=idx)
            job = integration.with_delay(**job_kwargs).import_stock_levels_integration(line)

            integration.job_log(job)

        return self.raise_notification()

    def raise_notification(self):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Import Stock Levels'),
                'message': 'Queue Jobs "Import Stock Levels" are created',
                'type': 'success',
                'sticky': False,
            },
        }


class ImportStockLevelsWizardLine(models.TransientModel):
    _name = 'import.stock.levels.wizard.line'
    _description = 'Import Stock Levels Wizard Line'

    wizard_id = fields.Many2one(
        comodel_name='import.stock.levels.wizard',
        string='Stock Level Wizard',
    )
    integration_id = fields.Many2one(
        comodel_name='sale.integration',
        related='wizard_id.integration_id',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        related='wizard_id.company_id',
    )
    location_id = fields.Many2one(
        string='Specify Location to import Stock',
        comodel_name='stock.location',
        required=True,
    )
    external_location_id = fields.Many2one(
        comodel_name='integration.stock.location.external',
        string='External Location',
    )
