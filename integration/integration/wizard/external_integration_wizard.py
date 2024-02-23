# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api


SET = 'set'
REMOVE = 'remove'
NO_CHANGE = 'no_change'

ROUTES = {
    SET: 4,  # adds an existing record of id to the set.
    REMOVE: 3,  # removes the record of id from the set, but does not delete it.
}


class ExternalIntegrationWizard(models.TransientModel):
    _name = 'external.integration.wizard'
    _description = 'External Integration Wizard'

    message = fields.Char(
        string='Message',
    )
    integration_line_ids = fields.One2many(
        comodel_name='external.integration.line',
        inverse_name='wizard_id',
        string='External Integration Lines',
    )

    @api.model
    def default_get(self, default_fields):
        values = super(ExternalIntegrationWizard, self).default_get(default_fields)

        active_integrations = self.env['sale.integration'].search([
            ('state', '=', 'active'),
        ])
        vals_list = [
            {'integration_id': x.id} for x in active_integrations
        ]
        integration_lines = self.integration_line_ids.create(vals_list)
        values['integration_line_ids'] = [(6, 0, integration_lines.ids)]

        return values

    def apply_integration(self):
        records = self._records_from_context()

        if not records:
            return self._close()

        for line in self.integration_line_ids:
            line._apply_to_records(records)

        return self._close()

    def _records_from_context(self):
        active_ids = self.env.context.get('active_ids')
        model_name = self.env.context.get('active_model')
        return self.env[model_name].browse(active_ids)

    def _close(self):
        return dict(type='ir.actions.act_window_close')


class ExternalIntegrationLine(models.TransientModel):
    _name = 'external.integration.line'
    _description = 'External Integration Line'

    def _get_integration_action_list(self):
        return [
            (NO_CHANGE, 'No Change'),
            (SET, 'Set'),
            (REMOVE, 'UnSet'),
        ]

    wizard_id = fields.Many2one(
        comodel_name='external.integration.wizard',
        string='Wizard',
    )
    integration_id = fields.Many2one(
        comodel_name='sale.integration',
        string='Sale integration',
        readonly=True,
    )
    name = fields.Char(
        related='integration_id.name',
    )
    integration_action = fields.Selection(
        selection=_get_integration_action_list,
        string='Action',
        default=NO_CHANGE,
    )

    def _apply_to_records(self, records):
        command = ROUTES.get(self.integration_action)

        if not command:
            return

        vals = dict(integration_ids=[(command, self.integration_id.id)])
        records.with_context(skip_product_export=True).write(vals)

        if self.integration_action == SET:
            if records._name == 'product.product':
                records = records.mapped('product_tmpl_id')

            records.with_context(skip_product_export=False).trigger_export(
                export_images=self.integration_id.allow_export_images,
                force_integrations=self.integration_id,
            )
