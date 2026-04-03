# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, _
from odoo.exceptions import UserError


class IntegrationOrderFieldMappingEditorWizard(models.TransientModel):
    _name = 'integration.order.field.mapping.editor.wizard'
    _description = 'Integration Order Field Mapping Editor Wizard'

    integration_id = fields.Many2one(
        string='E-Commerce Store',
        related='mapping_field_id.integration_id',
    )

    mapping_field_id = fields.Many2one(
        comodel_name='external.order.field.mapping',
        string='Order Field Mapping',
        help='Reference to order field mapping.'
    )

    external_order_field = fields.Char(
        related='mapping_field_id.external_order_field',
        string='External Order Field',
        readonly=False,
    )

    test_input_file_id = fields.Many2one(
        comodel_name='sale.integration.input.file',
        string='External Data File',
        domain="[('si_id', '=', integration_id)]",
        help='File to test the Python code against. Can be a JSON file from field Raw Data.'
    )

    integration_code = fields.Text(
        related='mapping_field_id.script',
        string='Code',
        readonly=False,
        help='Python code to execute.',
    )

    result = fields.Char(
        string='Result',
        readonly=True,
        help='Result of the executed Python code.'
    )

    def action_test(self):
        """Test the Python script with external JSON input and field path."""
        self.ensure_one()

        input_file = self.test_input_file_id

        if not input_file or not self.external_order_field:
            raise UserError(_('Please provide both an External Data File and an External Order Field.'))

        value = self.mapping_field_id.calculate_order_import_value(
            input_file.to_dict(),
            raise_error=True,
        )
        self.result = str(value)

        return self.open_form()

    def action_save_code(self):
        """Save the current code and external field to the mapping record."""
        self.ensure_one()

        if not self.mapping_field_id:
            raise UserError(_('No mapping record associated.'))

        self.mapping_field_id.write({
            'script': self.integration_code,
            'external_order_field': self.external_order_field,
        })

        return {'type': 'ir.actions.act_window_close'}

    def open_form(self):
        action = self.get_formview_action()
        action['target'] = 'new'
        return action
