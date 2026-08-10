# See LICENSE file for full copyright and licensing details.

from collections import Counter

from odoo import models, fields, _, api

from ..exceptions import ErrorStore as es


class RefreshProductStockWizard(models.TransientModel):
    _name = 'refresh.product.stock.wizard'
    _description = 'Refresh Product Stock from Store'

    template_id = fields.Many2one(
        comodel_name='product.template',
        string='Product',
        required=True,
    )
    allowed_integration_ids = fields.Many2many(
        comodel_name='sale.integration',
        string='Allowed E-Commerce Stores',
        compute='_compute_allowed_integration_ids',
    )
    integration_id = fields.Many2one(
        comodel_name='sale.integration',
        string='Refresh Stock from E-Commerce Store',
        domain="[('id', 'in', allowed_integration_ids)]",
    )
    supports_external_locations = fields.Boolean(
        related='integration_id.supports_external_locations',
        readonly=True,
    )
    mapped_erp_location_ids = fields.Many2many(
        comodel_name='stock.location',
        compute='_compute_mapped_location_ids',
        string='Mapped Odoo Locations',
    )
    mapped_external_location_ids = fields.Many2many(
        comodel_name='integration.stock.location.external',
        compute='_compute_mapped_location_ids',
        string='Mapped External Locations',
    )
    location_id = fields.Many2one(
        comodel_name='stock.location',
        string='Odoo Location',
        domain="[('id', 'in', mapped_erp_location_ids)]",
    )
    wizard_line_ids = fields.One2many(
        comodel_name='refresh.product.stock.wizard.line',
        inverse_name='wizard_id',
        string='Inventory Location Mapping',
    )
    supports_stock_fetch_by_product = fields.Boolean(
        related='integration_id.supports_stock_fetch_by_product',
        readonly=True,
    )

    @property
    def variant_ids(self):
        return self.template_id.product_variant_ids

    @api.depends('template_id.product_variant_ids.integration_ids')
    def _compute_allowed_integration_ids(self):
        for rec in self:
            integration_ids = rec.template_id.product_variant_ids.mapped(
                'integration_ids'
            )
            rec.allowed_integration_ids = integration_ids.filtered(
                lambda integration: integration.state == 'active'
            )

    @api.depends('integration_id')
    def _compute_mapped_location_ids(self):
        for rec in self:
            if not rec.integration_id:
                rec.mapped_erp_location_ids = False
                rec.mapped_external_location_ids = False
            else:
                lines = rec.integration_id.get_location_mappings()
                rec.mapped_erp_location_ids = lines.mapped('erp_location_id')
                rec.mapped_external_location_ids = lines.mapped('external_location_id')

    @api.onchange('integration_id')
    def _onchange_integration_id(self):
        for rec in self:
            rec.update(rec._prepare_defaults())

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        for rec in records:
            if not rec.integration_id:
                rec.integration_id = rec._get_default_integration()

            rec.write(rec._prepare_defaults())

        return records

    def _get_default_integration(self):
        self.ensure_one()

        integrations = self.allowed_integration_ids
        if len(integrations) == 1:
            return integrations

        return self.env['sale.integration']

    def _prepare_defaults(self):
        """Prepare default wizard values for the selected integration."""
        integration = self.integration_id
        if not integration:
            return {
                'location_id': False,
                'wizard_line_ids': [(5, 0, 0)],
            }

        location_lines = integration.get_location_mappings()
        valid_location_lines = location_lines.filtered('erp_location_id')

        values = {
            'location_id': valid_location_lines[:1].erp_location_id.id or False,
            'wizard_line_ids': [(5, 0, 0)],
        }
        if integration.supports_external_locations:
            valid_location_lines = valid_location_lines.filtered('external_location_id')
            values['wizard_line_ids'] = [(5, 0, 0)] + [
                (0, 0, {
                    'erp_location_id': line.erp_location_id.id,
                    'external_location_id': line.external_location_id.id,
                })
                for line in valid_location_lines
            ]

        return values

    def _get_mapped_variants(self):
        """Return variants mapped to the selected integration."""
        return self.variant_ids.filtered(lambda x: self.integration_id in x.integration_ids)

    def _get_refresh_location_pairs(self):
        """Return validated Odoo/external location pairs for stock refresh."""
        integration = self.integration_id
        location_lines = integration.get_location_mappings(raise_error=True)

        if not integration.supports_external_locations:
            if not self.location_id:
                raise es.UserError(_('Please select Odoo location to update.'))

            mapped_locations = location_lines.mapped('erp_location_id')
            if self.location_id not in mapped_locations:
                raise es.UserError(_(
                    'Selected Odoo location is not mapped on Inventory tab for store "%s".'
                ) % integration.name)

            return [(self.location_id, False)]

        selected_lines = self.wizard_line_ids
        if not selected_lines:
            raise es.UserError(_(
                'No mapping lines selected in this wizard.\n\n'
                'Please keep at least one mapping line or cancel this operation.'
            ))

        # Check for duplicates (import-only validation)
        self._check_one_to_one(selected_lines)

        return [
            (line.erp_location_id, line.external_location_id.code)
            for line in selected_lines
        ]

    def _get_stock_levels_data(self, external_location_code, external_variants):
        """Return stock levels for the selected mapped products."""
        if not external_variants:
            return {}

        adapter = self.integration_id.adapter
        if external_location_code:
            stock_levels_data = adapter.get_stock_levels(external_location_code)
        else:
            stock_levels_data = adapter.get_stock_levels()

        if not isinstance(stock_levels_data, dict):
            return stock_levels_data

        expected_external_codes = set(external_variants.mapped('code'))
        return {
            external_code: qty
            for external_code, qty in stock_levels_data.items()
            if external_code in expected_external_codes
        }

    def _get_mapped_external_variants(self, variants):
        """Return mapped external variants for the selected integration."""
        external_variants = self.env['integration.product.product.external']
        for variant in variants:
            external_variants |= variant.to_external_record(self.integration_id, raise_error=False)

        return external_variants.filtered('code')

    def _check_one_to_one(self, lines):
        """Check that location mappings have one-to-one relationships.

        Validates that neither Odoo locations nor external locations are
        duplicated across the selected mapping lines. This is required for
        the import process to correctly determine which location to update.
        """
        if not lines:
            return

        errors = []

        for field_name, label in (
            ('erp_location_id', _('Odoo location')),
            ('external_location_id', _('External location')),
        ):
            value_ids = [line[field_name].id for line in lines if line[field_name]]
            if not value_ids:
                continue

            value_counts = Counter(value_ids)

            duplicate_ids = [value_id for value_id, count in value_counts.items() if count > 1]

            if duplicate_ids:
                duplicate_records = self.env[lines._fields[field_name].comodel_name].browse(duplicate_ids)
                names = ', '.join(duplicate_records.mapped('display_name'))
                errors.append(
                    _('%(label)s duplicated: %(names)s') % {
                        'label': label,
                        'names': names,
                    }
                )

        if errors:
            raise es.UserError(_(
                'One-to-one mapping validation failed:\n\n'
                '%(errors)s\n\n'
                'Please remove duplicate rows and ensure each location '
                'is mapped only once before refreshing stock.'
            ) % {'errors': '\n'.join(f'• {error}' for error in errors)})

    def open_form(self):
        self.ensure_one()

        return {
            'name': _('Refresh Stock from Store'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': self._name,
            'res_id': self.id,
            'target': 'new',
        }

    def _get_refresh_variant_data(self):
        """Return external variants and skipped variant count for stock refresh."""
        mapped_variants = self._get_mapped_variants()
        external_variants = self._get_mapped_external_variants(mapped_variants)
        skipped_variant_count = len(self.variant_ids - mapped_variants)

        return external_variants, skipped_variant_count

    def run_refresh_stock(self):
        """Refresh stock for mapped product variants from the selected store."""
        self.ensure_one()

        integration = self.integration_id
        if not integration:
            raise es.UserError(_('Please select E-Commerce Store to refresh stock from.'))

        if integration not in self.allowed_integration_ids:
            raise es.UserError(_(
                'The selected E-Commerce Store is inactive or is not connected to this product.'
            ))

        integration = integration.with_context(company_id=integration.company_id.id)

        external_variants, skipped_variant_count = self._get_refresh_variant_data()
        stock_update_count = 0

        if external_variants:
            refresh_location_pairs = self._get_refresh_location_pairs()
            for location, external_location_code in refresh_location_pairs:
                stock_levels_data = self._get_stock_levels_data(external_location_code, external_variants)
                if not isinstance(stock_levels_data, dict):
                    raise es.UserError(_(
                        'Unable to refresh stock from store "%(integration)s".\n\n'
                        'The connector returned an unexpected stock response format.\n'
                        'Please verify connector configuration and try again. If the issue persists, contact support.'
                    ) % {'integration': integration.name})

                for external_code, qty in stock_levels_data.items():
                    if qty is None:
                        continue

                    integration._integration_apply_stock_qty(location, external_code, qty)
                    stock_update_count += 1

        if stock_update_count:
            message = _('Stock refresh scheduled for %s stock update(s).') % stock_update_count
            if skipped_variant_count:
                message += _(
                    ' %s variant(s) skipped because they are not mapped to this store.'
                ) % skipped_variant_count

            notif_type = 'success'
        else:
            if external_variants:
                message = _('No stock values were found in the selected store for mapped product variants.')
            else:
                message = _('No mapped product variants were found for the selected store.')
            if skipped_variant_count:
                message += _(
                    ' %s variant(s) skipped because they are not mapped to this store.'
                ) % skipped_variant_count

            notif_type = 'warning'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Refresh Stock from Store'),
                'message': message,
                'type': notif_type,
                'sticky': False,
            },
        }


class RefreshProductStockWizardLine(models.TransientModel):
    _name = 'refresh.product.stock.wizard.line'
    _description = 'Refresh Product Stock Wizard Line'

    wizard_id = fields.Many2one(
        comodel_name='refresh.product.stock.wizard',
        required=True,
        ondelete='cascade',
    )
    integration_id = fields.Many2one(
        comodel_name='sale.integration',
        related='wizard_id.integration_id',
        readonly=True,
    )
    erp_location_id = fields.Many2one(
        comodel_name='stock.location',
        string='Odoo Location',
        required=True,
        domain="[('id', 'in', wizard_id.mapped_erp_location_ids)]",
    )
    external_location_id = fields.Many2one(
        comodel_name='integration.stock.location.external',
        string='External Location',
        required=True,
        domain="[('id', 'in', wizard_id.mapped_external_location_ids)]",
    )
