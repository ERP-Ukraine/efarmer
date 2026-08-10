# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _


NO_CHANGE = 'no_change'
LINK = 'link'
LINK_EXPORT = 'link_export'
UNLINK = 'unlink'

# Many2many command per action: 4 = link (add), 3 = unlink (remove, without deleting).
ROUTES = {
    LINK: 4,
    LINK_EXPORT: 4,
    UNLINK: 3,
}


class ExternalIntegrationWizard(models.TransientModel):
    _name = 'external.integration.wizard'
    _description = 'External Integration Wizard'

    message = fields.Text(
        string='Message',
    )
    confirmation_message = fields.Text(
        string='Confirmation Message',
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('confirm', 'Confirm'),
        ],
        default='draft',
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

        # Any "Link & export now" action publishes products to a store (overwriting its content), so ask for an
        # explicit confirmation before doing anything. Pure link/unlink actions never push and are applied directly.
        if self.state == 'draft' and self._has_export_action():
            return self._open_confirmation(records)

        for line in self.integration_line_ids:
            line._apply_to_records(records)

        return self._close()

    def action_back(self):
        self.state = 'draft'
        return self._reopen()

    def _has_export_action(self):
        return any(line.integration_action == LINK_EXPORT for line in self.integration_line_ids)

    def _open_confirmation(self, records):
        export_integrations = self.integration_line_ids \
            .filtered(lambda line: line.integration_action == LINK_EXPORT) \
            .mapped('integration_id')

        self.write({
            'state': 'confirm',
            'confirmation_message': _(
                '%(products)s product(s) will be published now to: %(stores)s.\n'
                'This overwrites their existing content and images in those stores and cannot be undone. '
                'Click "Confirm export" to proceed, or "Back" to review your choices.'
            ) % {
                'products': len(records),
                'stores': ', '.join(export_integrations.mapped('name')),
            },
        })
        return self._reopen()

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Manage Store Connections'),
            'res_model': 'external.integration.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }

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
            (NO_CHANGE, 'No change'),
            (LINK, 'Link only'),
            (LINK_EXPORT, 'Link & export now'),
            (UNLINK, 'Unlink'),
        ]

    wizard_id = fields.Many2one(
        comodel_name='external.integration.wizard',
        string='Wizard',
    )
    integration_id = fields.Many2one(
        comodel_name='sale.integration',
        string='E-Commerce Store',
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

        # Linking/unlinking only changes membership; it never pushes (`skip_product_export=True`).
        vals = dict(integration_ids=[(command, self.integration_id.id)])
        records.with_context(skip_product_export=True).write(vals)

        if self.integration_action == LINK_EXPORT:
            if records._name == 'product.product':
                records = records.mapped('product_tmpl_id')

            # Explicit, deliberate push — same path as the product form "Export to Stores" button.
            records.with_context(skip_product_export=False, manual_trigger=True).trigger_export(
                export_images=self.integration_id.allow_export_images,
                force_integrations=self.integration_id,
            )
