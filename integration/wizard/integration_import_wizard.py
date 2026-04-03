import base64

from odoo import api, fields, models, _
from odoo.exceptions import UserError


IMPORT_PROCESS_STATES = [
    ('choose_mode', 'Choose Import Mode'),
    # First-Time Import (Initial Setup)
    ('first_time_import_1', 'Welcome to First-Time Import'),
    ('first_time_import_2', 'Import Master Data (Required Before Importing Products)'),
    ('first_time_import_2_1', 'Background Jobs'),
    ('first_time_import_2_2', 'Master Data Import Results'),
    ('first_time_import_2_3', 'Unmapped Mappings Review'),
    ('first_time_import_3', 'Product Import'),
    ('first_time_import_3_1', 'Product Import: Validation Report'),
    ('first_time_import_3_2', 'Product Import: Configuration'),
    ('first_time_import_3_3', 'Product Import: Background Jobs'),
    ('first_time_import_3_4', 'Product Import: Import Results'),
    ('first_time_import_4', 'Final Steps: Product Mapping & What\'s Next'),
    # Update Import (After Initial Setup)
    ('update_import_1', 'Step 1: Welcome to Update Import'),
    ('update_import_2', 'Step 2: Configure Import'),
    ('update_import_2_1', 'Step 2.1: Validation Report'),
    ('update_import_3', 'Step 3: Import Results'),
]

IMPORT_PROCESS_STATES_DICT = dict(IMPORT_PROCESS_STATES)


class IntegrationImportEntity(models.Model):
    _name = 'integration.import.entity'
    _description = 'Integration Import Entity'
    _order = 'name asc'

    _sql_constraints = [
        (
            'unique_name_integration_type',
            'UNIQUE(name, integration_type)',
            'An import entity with this name and integration type already exists!'
        ),
    ]

    name = fields.Char(
        string='Name',
    )

    method_name = fields.Char(
        string='Method Name',
        help='Name of the method to call on the integration for importing this entity type.',
    )

    external_model = fields.Char(
        string='External Model',
        help='Name of the external model (e.g., integration.product.attribute.external).',
    )

    mapping_model = fields.Char(
        string='Mapping Model',
        help='Name of the mapping model (e.g., integration.product.attribute.mapping).',
    )

    # Some entities are available for all e-commerce systems (integration_type will be empty),
    # but some are available for specific e-commerce systems (e.g. Magento 2, PrestaShop, etc.)
    integration_type = fields.Selection(
        selection=[
            ('magento2', 'Magento 2'),
            ('prestashop', 'PrestaShop'),
            ('shopify', 'Shopify'),
            ('woocommerce', 'WooCommerce'),
        ],
    )

    is_master_data = fields.Boolean(
        string='Is Master Data',
        default=True,
        help=(
            'Indicates if this entity is master data (e.g., attributes, categories) or '
            'operational data (e.g., products, orders).',
        )
    )

    supports_import_by_id = fields.Boolean(
        string='Supports Import by ID',
        default=False,
        help='Indicates if this entity supports importing specific records by their external IDs.',
    )


class IntegrationImportWizard(models.TransientModel):
    _name = 'integration.import.wizard'
    _inherit = 'export.file.mixin'
    _description = 'Integration Import Wizard'

    state = fields.Selection(
        selection=IMPORT_PROCESS_STATES,
        string='State',
        default='choose_mode',
    )

    def _default_integration_id(self):
        """
        Fallback to the integration ID from the context.
        """
        return self.env.context.get('active_id')

    integration_id = fields.Many2one(
        string='E-Commerce Store',
        comodel_name='sale.integration',
        default=_default_integration_id,
        required=True,
    )

    integration_type = fields.Selection(
        related='integration_id.type_api',
        string='E-Commerce Store Type',
        readonly=True,
    )

    import_mode = fields.Selection(
        selection=[
            ('first_time', 'First-Time Import (Initial Setup)'),
            ('update', 'Update Import (After Initial Setup)'),
        ],
        string='Select Import Mode',
        required=True,
    )

    import_in_background = fields.Boolean(
        string='Import in Background',
        default=True,
    )

    remove_existing_records = fields.Boolean(
        string='Remove Existing External Records and Mappings',
        default=False,
    )

    jobs = fields.Many2many(
        comodel_name='queue.job',
        string='Jobs',
        readonly=True,
    )

    jobs_done = fields.Boolean(
        string='Jobs Done',
        compute='_compute_jobs_done',
    )

    jobs_failed = fields.Boolean(
        string='Jobs Failed',
        compute='_compute_jobs_failed',
    )

    entities_to_import = fields.Many2many(
        comodel_name='integration.import.entity',
        string='Entities to Import',
        domain=(
            '["|", '
            '("integration_type", "=", False), '
            '("integration_type", "=", integration_type), '
            '("is_master_data", "=", True)]'
        ),
    )

    entity_to_import = fields.Many2one(
        comodel_name='integration.import.entity',
        string='Entity to Import',
        domain=(
            '["|", '
            '("integration_type", "=", False), '
            '("integration_type", "=", integration_type)]'
        )
    )

    entity_supports_import_by_id = fields.Boolean(
        related='entity_to_import.supports_import_by_id',
        string='Supports Import by ID',
        readonly=True,
    )

    entity_external_model = fields.Char(
        related='entity_to_import.external_model',
        string='External Model',
        readonly=True,
    )

    external_ids = fields.Text(
        string='External IDs',
        help=(
            'Enter one or more external IDs (comma or line separated) to import specific records. '
            'Leave empty to import all records of the selected entity.'
        ),
    )

    results = fields.Html(
        string='Results',
        readonly=True,
        help='Information about import results.',
    )

    errors = fields.Html(
        string='Errors',
        readonly=True,
        help='Errors during the import.',
    )

    accept_unmapped_mappings = fields.Boolean(
        string='I understand the risks of skipping unmapped mappings',
        default=False,
    )

    accept_validation_failures = fields.Boolean(
        string='I understand the risks of proceeding with unresolved issues',
        default=False,
    )

    def _compute_jobs_done(self):
        for record in self:
            record.jobs_done = all(job.state == 'done' for job in record.jobs)

    def _compute_jobs_failed(self):
        for record in self:
            record.jobs_failed = any(job.state == 'failed' for job in record.jobs)

    @api.onchange('integration_id')
    def _onchange_integration_id(self):
        if self.integration_id:
            domain = [
                '|',
                ('integration_type', '=', False),
                ('integration_type', '=', self.integration_type),
                ('is_master_data', '=', True),
            ]
            self.entities_to_import = self.env['integration.import.entity'].search(domain, order='name asc')
        else:
            self.entities_to_import = [(5, 0, 0)]  # Clear the field if no integration

    @api.onchange('entity_to_import')
    def _onchange_entity_to_import(self):
        if self.entity_to_import and not self.entity_to_import.supports_import_by_id:
            self.external_ids = ''

    @api.onchange('external_ids')
    def _onchange_external_ids(self):
        if self.external_ids:
            # Do not allow to remove existing records if external IDs are provided (i.e. import specific records by ID)
            self.remove_existing_records = False

    #
    # Actions
    #
    def action_choose_import_mode(self):
        self.state = 'first_time_import_1' if self.import_mode == 'first_time' else 'update_import_1'

        return {
            'type': 'ir.actions.act_window',
            'name': IMPORT_PROCESS_STATES_DICT[self.state],
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_start_initial_import(self):
        self.state = 'first_time_import_2'

        return {
            'type': 'ir.actions.act_window',
            'name': IMPORT_PROCESS_STATES_DICT[self.state],
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_back_to_choose_mode(self):
        self.state = 'choose_mode'
        return {
            'type': 'ir.actions.act_window',
            'name': IMPORT_PROCESS_STATES_DICT[self.state],
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_import_master_data(self):
        if self.import_in_background:
            jobs = self.integration_id.import_master_data_in_background(
                self.entities_to_import,
                remove_existing_records=self.remove_existing_records,
            )
            self.jobs = jobs

            self.state = 'first_time_import_2_1'
            return {
                'type': 'ir.actions.act_window',
                'name': IMPORT_PROCESS_STATES_DICT[self.state],
                'res_model': self._name,
                'view_mode': 'form',
                'res_id': self.id,
                'target': 'new',
            }

        # Import records in real-time
        results = self.integration_id.import_master_data(
            self.entities_to_import,
            remove_existing_records=self.remove_existing_records,
        )

        # Format results into HTML
        self.results = self._format_master_data_import_results_html(results)

        self.state = 'first_time_import_2_2'
        return {
            'type': 'ir.actions.act_window',
            'name': IMPORT_PROCESS_STATES_DICT[self.state],
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_master_data_import_skip(self):
        # Check for unmapped mappings before proceeding
        if self.check_unmapped_mappings_before_product_import():
            # Show unmapped mappings information
            self.state = 'first_time_import_2_3'
            return {
                'type': 'ir.actions.act_window',
                'name': IMPORT_PROCESS_STATES_DICT[self.state],
                'res_model': self._name,
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
            }

        self.state = 'first_time_import_3'

        # Reset the remove_existing_records field
        self.remove_existing_records = False

        return {
            'type': 'ir.actions.act_window',
            'name': IMPORT_PROCESS_STATES_DICT[self.state],
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_back_to_import_master_data(self):
        self.state = 'first_time_import_2'
        return {
            'type': 'ir.actions.act_window',
            'name': IMPORT_PROCESS_STATES_DICT[self.state],
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_open_queue_jobs(self):
        queue_job_action = self.env.ref('integration.integration_job_log_action')
        return {
            'type': 'ir.actions.act_url',
            'url': f'/odoo/action-{queue_job_action.id}',
            'target': 'new',
        }

    def action_refresh_unmapped_records(self):
        self.check_unmapped_mappings_before_product_import()
        if not self.errors:
            return self.action_continue_to_product_import()
        return self.action_refresh_view()

    def download_pdf(self):
        pdf_bytes = self._convert_html_to_pdf_bytes(self.errors)
        self.export_pdf = base64.b64encode(pdf_bytes)
        return super().download_pdf()

    def action_refresh_view(self):
        # Do nothing, just return the same window with updated information (e.g. jobs statuses)
        return {
            'type': 'ir.actions.act_window',
            'name': IMPORT_PROCESS_STATES_DICT[self.state],
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_refresh_queue_jobs_view(self):
        child_jobs = self.env['queue.job'].search([
            ('parent_id', 'in', self.jobs.ids),
        ])
        self.jobs = child_jobs + self.jobs

        return self.action_refresh_view()

    def action_continue_to_product_import(self):
        if self.import_in_background and not self.jobs_done:
            raise UserError(_('Background jobs are still running. Please wait for them to finish.'))

        # Check for unmapped mappings before proceeding
        if self.check_unmapped_mappings_before_product_import():
            # Check if user has accepted the risks
            if not self.accept_unmapped_mappings:
                # Show unmapped mappings information
                self.state = 'first_time_import_2_3'
                return {
                    'type': 'ir.actions.act_window',
                    'name': IMPORT_PROCESS_STATES_DICT[self.state],
                    'res_model': self._name,
                    'view_mode': 'form',
                    'res_id': self.id,
                    'target': 'new',
                }

        # If there are no unmapped mappings or user has accepted the risks, proceed to product import
        self.state = 'first_time_import_3'

        # Reset the remove_existing_records field
        self.remove_existing_records = False

        return {
            'type': 'ir.actions.act_window',
            'name': IMPORT_PROCESS_STATES_DICT[self.state],
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_import_products(self):
        self.state = 'first_time_import_3_2'
        return {
            'type': 'ir.actions.act_window',
            'name': IMPORT_PROCESS_STATES_DICT[self.state],
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_back_to_product_import(self):
        self.state = 'first_time_import_3'
        return {
            'type': 'ir.actions.act_window',
            'name': IMPORT_PROCESS_STATES_DICT[self.state],
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_run_product_import(self):
        """
        Run product import based on the import_in_background checkbox.
        """
        self.ensure_one()

        if not self.integration_id:
            raise UserError(_('No integration selected.'))

        if self.import_in_background:
            jobs = self.integration_id.import_products_in_background(
                remove_existing_records=self.remove_existing_records,
            )
            self.jobs = jobs

            self.state = 'first_time_import_3_3'
            return {
                'type': 'ir.actions.act_window',
                'name': IMPORT_PROCESS_STATES_DICT[self.state],
                'res_model': self._name,
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
            }

        # Import products in real-time
        results = self.integration_id.import_products(
            remove_existing_records=self.remove_existing_records,
        )
        self.results = self._format_product_import_results_html(results)

        self.state = 'first_time_import_3_4'
        return {
            'type': 'ir.actions.act_window',
            'name': IMPORT_PROCESS_STATES_DICT[self.state],
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_finish_initial_import(self):
        """
        Show the last step with additional steps (e.g. customer import, etc.)
        """
        self.state = 'first_time_import_4'
        return {
            'type': 'ir.actions.act_window',
            'name': IMPORT_PROCESS_STATES_DICT[self.state],
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_open_product_mappings(self):
        """
        Open the product mappings screen.
        """
        return {
            'type': 'ir.actions.act_window',
            'name': 'Products Mappings',
            'res_model': 'integration.product.template.mapping',
            'view_mode': 'list',
            'context': {
                'search_default_not_mapped': 1,
            },
            'target': 'current',
        }

    def action_start_catalog_validation(self):
        validation_result = self.integration_id._get_product_validation_report_html()

        if validation_result:
            # Redirect to the validation report
            self.errors = validation_result
            self.state = 'first_time_import_3_1'
            return {
                'type': 'ir.actions.act_window',
                'name': IMPORT_PROCESS_STATES_DICT[self.state],
                'res_model': self._name,
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
            }

        # No errors, redirect to the product import
        self.state = 'first_time_import_3_2'
        return {
            'type': 'ir.actions.act_window',
            'name': IMPORT_PROCESS_STATES_DICT[self.state],
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_start_update_import(self):
        """
        Start the update import flow - show entity selection.
        """
        self.state = 'update_import_2'
        return {
            'type': 'ir.actions.act_window',
            'name': IMPORT_PROCESS_STATES_DICT[self.state],
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_run_update_import(self):
        """
        Run entity import
        """
        entity = self.entity_to_import

        if not entity:
            raise UserError(_('No entity selected. Please select an entity to import.'))

        external_ids = None
        if entity.supports_import_by_id and self.external_ids:
            # Import specific records by ID
            external_ids = self._parse_external_ids(self.external_ids)

        if not entity.method_name:
            raise UserError(
                _('Import for entity "%s" can\'t be run because it is not implemented yet. '
                    'This is technical exception, please contact our support if you see this message: '
                    'https://support.ventor.tech') % entity.name,
            )

        method = getattr(self.integration_id, entity.method_name, None)
        if not method:
            raise UserError(
                _('Import for entity "%s" can\'t be run because it is not implemented yet. '
                    'This is technical exception, please contact our support if you see this message: '
                    'https://support.ventor.tech') % entity.name,
            )

        if entity.external_model == 'integration.product.template.external':
            validation_result = self.integration_id._get_product_validation_report_html()

            if validation_result:
                # Redirect to the validation report
                self.errors = validation_result
                self.state = 'update_import_2_1'
                return {
                    'type': 'ir.actions.act_window',
                    'name': IMPORT_PROCESS_STATES_DICT[self.state],
                    'res_model': self._name,
                    'res_id': self.id,
                    'view_mode': 'form',
                    'target': 'new',
                }

            # No errors, continue to the update import products
            return self.action_update_import_products()

        if entity.supports_import_by_id:
            result = method(
                external_ids=external_ids,
                # Do not allow to remove existing records if external IDs are provided
                # (i.e. import specific records by ID)
                remove_existing_records=False,
            )
        else:
            result = method(
                remove_existing_records=self.remove_existing_records,
            )

        # Format results into HTML
        self.results = self._format_external_records_import_results_html(
            result,
            entity_name=entity.name,
        )

        self.state = 'update_import_3'

        return {
            'type': 'ir.actions.act_window',
            'name': IMPORT_PROCESS_STATES_DICT[self.state],
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_update_import_products(self):
        """
        Update product imports without validation.
        """
        entity = self.env['integration.import.entity'].search([
            ('external_model', '=', 'integration.product.template.external')
        ], limit=1)

        external_ids = None
        if self.external_ids:
            # Import specific records by ID
            external_ids = self._parse_external_ids(self.external_ids)

        method = getattr(self.integration_id, entity.method_name, None)

        if external_ids:
            # Do not allow to remove existing records if external IDs are provided
            # (i.e. import specific records by ID)
            result = method(
                external_ids=external_ids,
                remove_existing_records=False,
            )
        else:
            result = method(remove_existing_records=self.remove_existing_records)

        # For products we have special format to provide more information
        # about imported products
        self.results = self._format_product_import_results_html(result)

        self.state = 'update_import_3'

        return {
            'type': 'ir.actions.act_window',
            'name': IMPORT_PROCESS_STATES_DICT[self.state],
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_back_to_update_import(self):
        """
        Go back to the update import start.
        """
        self.state = 'update_import_1'
        return {
            'type': 'ir.actions.act_window',
            'name': IMPORT_PROCESS_STATES_DICT[self.state],
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def check_unmapped_mappings_before_product_import(self):
        """
        Check if there are any unmapped records in the integration.
        If unmapped records exist, set errors with unmapped records info and
        return True to show the information.
        Otherwise, return False to proceed normally.
        """
        if not self.integration_id:
            return False

        unmapped_mappings = self.integration_id.get_unmapped_mappings()

        if unmapped_mappings:
            # Format unmapped mappings into HTML
            self.errors = self._format_unmapped_mappings_html(unmapped_mappings)
            return True

        self.errors = False
        return False

    #
    # Helper methods
    #
    def _parse_external_ids(self, external_ids_text):
        """
        Parse the input text and return a list of IDs.
        """
        if not external_ids_text:
            return []

        external_ids = [
            id.strip()
            for id in external_ids_text.replace(',', '\n').split('\n')
            if id.strip()
        ]
        return external_ids

    def _format_product_import_results_html(self, results):
        """
        Helper method to format the product import results into HTML.
        """
        html_result = '<div>'

        if results.get('message'):
            html_result += f'<div style="color: #f57c00; margin-bottom: 8px;">⚠️ {results["message"]}</div>'
            return html_result

        # Summary statistics
        html_result += '<div style="color: #388e3c; margin-bottom: 8px;"><strong>Import Summary:</strong></div>'
        html_result += '<div style="margin-left: 20px; margin-bottom: 8px;">'
        html_result += f'• Total processed: {results["total_processed"]}<br>'
        html_result += f'• Successful imports: {results["successful_imports"]}<br>'
        html_result += f'• Failed imports: {results["failed_imports"]}'
        html_result += '</div><br>'

        # Imported templates and variants (show first 20 + summary)
        if results.get('imported_templates'):
            templates = results['imported_templates']
            total_templates = len(templates)
            shown_templates = templates[:20]
            remaining_templates = total_templates - 20

            html_result += (
                '<div style="color: #388e3c; margin-bottom: 8px;">'
                f'    <strong>Imported Templates ({total_templates} total):</strong>'
                '</div>'
            )

            for template in shown_templates:
                if isinstance(template, dict):
                    # New structured format
                    html_result += (
                        '<div style="margin-left: 20px; margin-bottom: 4px;">'
                        f'    • {template["name"]} (ID: {template["code"]}, SKU: {template.get("external_reference", "-")})'  # NOQA
                        '</div>'
                    )
                else:
                    # Old string format (fallback)
                    html_result += f'<div style="margin-left: 20px; margin-bottom: 4px;">• {template}</div>'

            if remaining_templates > 0:
                html_result += (
                    '<div style="margin-left: 20px; margin-bottom: 4px; color: #666; font-style: italic;">'
                    f'    ... and {remaining_templates} more templates'
                    '</div>'
                )

            html_result += '<br>'

        if results.get('imported_variants'):
            variants = results['imported_variants']
            total_variants = len(variants)
            shown_variants = variants[:20]
            remaining_variants = total_variants - 20

            html_result += (
                '<div style="color: #388e3c; margin-bottom: 8px;">'
                f'    <strong>Imported Variants ({total_variants} total):</strong>'
                '</div>'
            )

            for variant in shown_variants:
                if isinstance(variant, dict):
                    # New structured format
                    html_result += (
                        '<div style="margin-left: 20px; margin-bottom: 4px;">'
                        f'    • {variant["name"]} (ID: {variant["code"]}, SKU: {variant.get("external_reference", "-")})'  # NOQA
                        '</div>'
                    )
                else:
                    # Old string format (fallback)
                    html_result += f'<div style="margin-left: 20px; margin-bottom: 4px;">• {variant}</div>'

            if remaining_variants > 0:
                html_result += (
                    '<div style="margin-left: 20px; margin-bottom: 4px; color: #666; font-style: italic;">'
                    f'    ... and {remaining_variants} more variants'
                    '</div>'
                )

            html_result += '<br>'

        # Errors (also limit to first 20 for performance)
        if results.get('errors'):
            errors = results['errors']
            total_errors = len(errors)
            shown_errors = errors[:20]
            remaining_errors = total_errors - 20

            html_result += (
                '<div style="color: #d32f2f; margin-bottom: 8px;">'
                f'    <strong>Errors ({total_errors} total):</strong>'
                '</div>'
            )

            for error in shown_errors:
                html_result += f'<div style="color: #d32f2f; margin-left: 20px; margin-bottom: 4px;">• {error}</div>'

            if remaining_errors > 0:
                html_result += (
                    '<div style="margin-left: 20px; margin-bottom: 4px; color: #666; font-style: italic;">'
                    f'    ... and {remaining_errors} more errors'
                    '</div>'
                )

        html_result += '</div>'
        return html_result

    def _format_external_records_import_results_html(self, external_records, entity_name=None):
        """
        Helper method to format the external records import results into HTML.

        Args:
            external_records: Recordset of external records (e.g., integration.product.attribute.external)
            entity_name: Optional name of the entity being imported (e.g., "Attributes", "Categories")

        Returns:
            str: HTML formatted results
        """
        if not external_records:
            return '<div><div style="color: #f57c00; margin-bottom: 8px;">⚠️ No records were imported.</div></div>'

        # Get entity name from the first record if not provided
        if not entity_name:
            entity_name = external_records[0]._description or "Records"

        html_result = '<div>'

        # Summary statistics
        total_records = len(external_records)
        html_result += '<div style="color: #388e3c; margin-bottom: 8px;"><strong>Import Summary:</strong></div>'
        html_result += '<div style="margin-left: 20px; margin-bottom: 8px;">'
        html_result += f'• Total imported: {total_records} {entity_name.lower()}<br>'
        html_result += '</div><br>'

        # Imported records (show first 20 + summary)
        shown_records = external_records[:20]
        remaining_records = total_records - 20

        html_result += (
            '<div style="color: #388e3c; margin-bottom: 8px;">'
            f'    <strong>Imported {entity_name} ({total_records} total):</strong>'
            '</div>'
        )

        for record in shown_records:
            # Format each record with available fields
            record_info = self._format_external_record_info(record)
            html_result += f'<div style="margin-left: 20px; margin-bottom: 4px;">• {record_info}</div>'

        if remaining_records > 0:
            html_result += (
                '<div style="margin-left: 20px; margin-bottom: 4px; color: #666; font-style: italic;">'
                f'    ... and {remaining_records} more {entity_name.lower()}'
                '</div>'
            )

        html_result += '</div>'
        return html_result

    def _format_master_data_import_results_html(self, results):
        """
        Helper method to format the master data import results into HTML.

        Args:
            results: Dictionary containing import results for each entity

        Returns:
            str: HTML formatted results
        """
        html_results = '''
        <div class="table-responsive">
            <table class="table table-sm table-bordered text-center">
                <thead class="table-light">
                    <tr>
                        <th style="width: 30%;">Entity</th>
                        <th style="width: 15%;">Status</th>
                        <th style="width: 55%;">Details</th>
                    </tr>
                </thead>
                <tbody>
        '''

        for entity_name, result in results.items():
            status = result["status"]
            if status == 'error':
                status_cell = '❌ Error'
                details = f'Error: {result["error"]}'
            elif status == 'skipped':
                status_cell = '⚠️ Skipped'
                details = f'Reason: {result["reason"]}'
            elif status == 'success':
                count = len(result["result"]) if "result" in result else 0
                status_cell = '✅ Success'
                details = f'Imported {count} records'
            else:
                status_cell = '❓ Unknown'
                details = 'Unknown status'

            html_results += f'''
                    <tr>
                        <td><strong>{entity_name}</strong></td>
                        <td>{status_cell}</td>
                        <td>{details}</td>
                    </tr>
            '''

        html_results += '''
                </tbody>
            </table>
        </div>
        '''
        return html_results

    def _format_external_record_info(self, record):
        """
        Format a single external record for display in HTML.

        Args:
            record: External record (e.g., integration.product.attribute.external)

        Returns:
            str: Formatted record information
        """
        # Get the display name or name field
        display_name = getattr(record, 'display_name', None)
        if not display_name:
            display_name = getattr(record, 'name', 'Unnamed Record')

        # Build the record info string
        record_info = f'{display_name}'

        # Add external reference if available
        if hasattr(record, 'external_reference') and record.external_reference:
            record_info += f' (Ref: {record.external_reference})'

        # Add mapping status if available
        if hasattr(record, 'mapping_record') and record.mapping_record:
            odoo_record = record.odoo_record
            if odoo_record:
                record_info += f' → Mapped to: {odoo_record.display_name}'
            else:
                record_info += ' → Not Mapped'
        else:
            record_info += ' → No Mapping'

        return record_info

    def _format_unmapped_mappings_html(self, unmapped_mappings):
        """
        Helper method to format the unmapped mappings into HTML.

        Args:
            unmapped_mappings: List of dictionaries containing unmapped mapping information

        Returns:
            str: HTML formatted unmapped mappings table
        """
        table_rows = '''
            <div class="table-responsive">
                <table class="table table-sm table-bordered text-center">
                    <thead class="table-light">
                        <tr>
                            <th style="width: 50%;">Entity Type</th>
                            <th style="width: 50%;">Unmapped Records</th>
                        </tr>
                    </thead>
                    <tbody>
        '''

        for mapping in unmapped_mappings:
            table_rows += f'''
                <tr>
                    <td><strong>{mapping['name']}</strong></td>
                    <td><span class="badge bg-warning text-dark">{mapping['count']} records</span></td>
                </tr>
            '''

        table_rows += '''
                    </tbody>
                </table>
            </div>
        '''
        return table_rows
