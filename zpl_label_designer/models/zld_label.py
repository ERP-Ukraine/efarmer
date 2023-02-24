import re

from odoo import api, exceptions, fields, models, _
from odoo.tools.safe_eval import safe_eval


PLACEHOLDER_REGEX = r'\%\%[a-z_\d\.]+?\%\%'
FIELD_PLACEHOLDER = '<t t-esc="doc.{}"/>'
TEMPLATE_BASE = '<t t-foreach="docs" t-as="doc">{content}</t>'
SPECIAL_CHARACTERS = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
}


class Label(models.Model):
    _name = 'zld.label'
    _description = 'ZPL Designer Label'

    name = fields.Char(
        string='Name',
        required=True,
        readonly=True,
    )

    zpl = fields.Text(
        string="ZPL",
        default='',
        readonly=True,
    )

    preview = fields.Text(
        string="Preview (with demo data)",
        default=False,
        readonly=True,
    )

    width = fields.Float(
        string="Width, inch",
        default=5,
        required=True,
        readonly=True,
    )

    height = fields.Float(
        string="Height, inch",
        default=2.5,
        required=True,
        readonly=True,
    )

    dpi = fields.Integer(
        string="DPI",
        required=True,
        readonly=True,
    )

    orientation = fields.Char(
        string="Orientation",
        readonly=True,
    )

    is_published = fields.Boolean(
        string="Is Published?",
        default=False,
        copy=False,
    )

    is_modified = fields.Boolean(
        string="Is Modified After Publishing?",
        default=False,
    )

    action_report_id = fields.Many2one(
        comodel_name='ir.actions.report',
        string='Related ir.actions.report ID',
        copy=False,
    )

    view_id = fields.Many2one(
        comodel_name='ir.ui.view',
        string='Related ir.ui.view ID',
        copy=False,
    )

    model_id = fields.Many2one(
        comodel_name='ir.model',
        string='Label Model',
        ondelete='cascade',
        required=True,
        readonly=True,
    )

    print_report_name = fields.Char(
        string='Report Name',
        help=(
            'This field allows to set custom print report name.'
            'There can be any valid Python expression.'
            'If empty, label name will be used.'
        ),
    )

    print_report_name_preview = fields.Char(
        string='Report Name Preview',
        compute='_compute_print_report_name_preview',
    )

    designer_label_id = fields.Char(
        string='Designer Label ID',
        readonly=True,
    )

    @api.depends('name', 'print_report_name')
    def _compute_print_report_name_preview(self):
        for rec in self:
            if rec.print_report_name:
                random_record = rec._get_random_record(rec.zpl, rec.model_id.model)
                rec.print_report_name_preview = safe_eval(
                    rec.print_report_name,
                    {'object': random_record}
                )
            else:
                rec.print_report_name_preview = rec.name

    @api.onchange('print_report_name')
    def _onchange_print_report_name(self):
        if self.print_report_name:
            # Check if expression is valid
            try:
                self._compute_print_report_name_preview()
            except Exception as e:
                raise exceptions.ValidationError(
                    _('Invalid Print Report Name expression: {}').format(e)
                )

    def copy(self, default=None):
        raise exceptions.UserError(_(
            "You can't duplicate a label. Please, go to the ZPL Label Designer to create labels."
        ))

    def unlink(self):
        for label in self:
            if label.is_published:
                raise exceptions.UserError(_('Cannot delete published label'))

            if not self.env.is_superuser() and label.designer_label_id:
                raise exceptions.UserError(_(
                    "You can't delete a label from Odoo that is synced with labels.ventor.tech. "
                    "Please, go to the labels.ventor.tech to do this."
                ))

        return super().unlink()

    #
    # Button actions
    #
    def publish(self):
        """
        This method publish label to Odoo. It creates (or updates) ir.action.report and ir.ui.view.
        """
        self.ensure_one()

        # Validate label before publishing
        self._validate_placeholders(self.zpl, self.model_id.model)

        if not self.zpl.strip():  # Strip is just in case
            raise exceptions.UserError(
                _('Label is empty. Please add at least one element to the label'))

        if self.action_report_id:
            # Label already published. Do update of label content and exit
            self._update_label_content()

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Label was updated'),
                    'message': _('Label {} was successfully updated').format(self.name),
                    'type': 'success',
                    'sticky': False,
                    'next': {
                        'type': 'ir.actions.client',
                        'tag': 'reload',
                    }
                },
            }

        view_xmlid = f'zpl_label_designer.{self.model_id.model.replace(".", "_")}_label_{self.id}'
        label_view_id = self.env['ir.ui.view'].create({
            'type': 'qweb',
            'arch': self._prepare_label_template(),
            'name': view_xmlid,
            'key': view_xmlid
        })
        self.env['ir.model.data'].create({
            'module': 'zpl_label_designer',
            'name': view_xmlid,
            'model': 'ir.ui.view',
            'res_id': label_view_id.id,
            # Make it no updatable to avoid deletion on module upgrade
            'noupdate': True,
        })

        self.view_id = label_view_id

        action_xmlid = f'zpl_label_designer.{self.model_id.model.replace(".", "_")}_label_action_{self.id}'  # NOQA
        label_action_report = self.env['ir.actions.report'].create({
            'xml_id': action_xmlid,
            'name': self.name,
            'model': self.model_id.model,
            'report_type': 'qweb-text',
            'report_name': view_xmlid,
            'report_file': view_xmlid,
            'print_report_name': self.print_report_name or f"'{self.name}'",
            'binding_model_id': self.model_id.id,
            'binding_type': 'report',
        })
        self.env['ir.model.data'].create({
            'module': 'zpl_label_designer',
            'name': action_xmlid,
            'model': 'ir.actions.report',
            'res_id': label_action_report.id,
            # Make it no updatable to avoid deletion on module upgrade
            'noupdate': True,
        })

        self.action_report_id = label_action_report
        self.is_published = True

        return True

    def unpublish(self):
        self.ensure_one()

        if self.action_report_id:
            self.action_report_id.unlink()
            self.view_id.unlink()

        self.is_published = False

        return True

    def update_published_label(self):
        self.publish()
        self.is_modified = False

    def open_view(self):
        self.ensure_one()

        if not self.view_id:
            raise exceptions.UserError(_('Label is not published'))

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ir.ui.view',
            'res_id': self.view_id.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'no_breadcrumbs': False,
            }
        }

    def open_in_designer(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_url',
            'url': self.get_label_designer_url(self.designer_label_id),
            'target': 'blank',
        }

    def update_demo(self):
        """
        This method update label preview with demo data.
        """
        self.ensure_one()
        self.preview = self.generate_demo(self.zpl, self.model_id.model)

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    #
    # Public methods
    #
    @api.model
    def create_label(self, attrs):
        # Replace model with model_id. It's a bit hacky but for now it's the easiest way
        model_name = attrs.get('model')
        if not model_name:
            raise exceptions.UserError(_('Model is not specified'))

        del attrs['model']

        attrs['model_id'] = self.env['ir.model'].search([('model', '=', model_name)]).id
        label = self.create([attrs])

        label.update_demo()

        return label.id

    @api.model
    def update_label(self, label_id, attrs):
        # Use exists to make sure that label really exists
        label = self.browse(label_id).exists()

        if not label:
            # Create new label if it doesn't exist
            label_id = self.create_label(attrs)
            return label_id

        attrs.pop('model', None)  # Model can not be changed, used only on create
        label.write(attrs)

        label.update_demo()
        label.is_modified = True

        return label.id

    @api.model
    def delete_label(self, label_id):
        label = self.browse(label_id).exists()

        if not label:
            # TODO: Maybe it's better just to return success?
            raise ValueError(_('Not label with such ID found in Odoo'))

        # This will raise exception if label published
        label.unlink()

    @api.model
    def generate_demo(self, zpl, model_name):
        """
        This method replaces placeholders with demo data.
        """
        label_preview = zpl

        # Validate label before generating preview
        self._validate_placeholders(zpl, model_name)

        random_record = self._get_random_record(zpl, model_name)

        placeholders = re.findall(PLACEHOLDER_REGEX, label_preview)
        # Replace placeholders with data
        for placeholder in placeholders:
            placeholder_attr = placeholder[2:-2]  # Remove %% from start and end

            # Record is object from DB for current placeholder level of nesting
            # Original level is 0 (record of current model of label)
            record_for_current_level = random_record

            while '.' in placeholder_attr:
                field, placeholder_attr = placeholder_attr.split('.', 1)
                record_for_current_level = getattr(record_for_current_level, field)

            placeholder_value = str(getattr(record_for_current_level, placeholder_attr, ''))

            label_preview = label_preview.replace(placeholder, placeholder_value)

        return label_preview

    #
    # Internal methods
    #
    def _validate_placeholders(self, zpl, model_name):
        """
        This method validates placeholders in label design.
        """
        placeholders = re.findall(PLACEHOLDER_REGEX, zpl)
        Model = self.env[model_name]

        for placeholder in placeholders:
            placeholder_attr = placeholder[2:-2]  # Remove %% from start and end

            # Starting from level 0 (model of current label)
            FieldModel = Model

            while '.' in placeholder_attr:
                field, placeholder_attr = placeholder_attr.split('.', 1)

                # No nested field name specified
                if not placeholder_attr:
                    raise exceptions.ValidationError(
                        _('Invalid placeholder: "{}"').format(placeholder))

                # Field doesn't exist
                if field not in FieldModel._fields:
                    raise exceptions.UserError(
                        _('Field "{}" does not exist in "{}" model').format(
                            field, FieldModel._description)
                    )

                # Field is not Many2one
                if FieldModel._fields[field].type != 'many2one':
                    raise exceptions.UserError(
                        _(
                            'Field "{}" is not a many2one field and '
                            'can not be used to get nested fields'
                        ).format(field)
                    )

                FieldModel = self.env[FieldModel._fields[field].comodel_name]

            # Finally, check if target field exists
            if placeholder_attr not in FieldModel._fields:
                raise exceptions.UserError(
                    _('Field "{}" does not exist in "{}" model').format(
                        placeholder_attr, FieldModel._name)
                )

        return True

    def _get_random_record(self, zpl, model_name):
        """
        This method returns random record from model
        (tries to find record with fields that are not empty)
        """
        placeholders = re.findall(PLACEHOLDER_REGEX, zpl)

        # Try to find objects with not empty fields
        not_empty_fields = [p[2:-2] for p in placeholders]
        domain = [(f, '!=', False) for f in not_empty_fields]
        random_record = self.env[model_name].search(domain, limit=1)

        if not random_record:
            # If no object found, try to find any object
            random_record = self.env[model_name].search([], limit=1)

        return random_record

    def _prepare_label_template(self):
        self.ensure_one()

        # Replace placeholders with qweb fields
        label_content = self.zpl

        # Replace special characters in placeholders with html entities
        for char, replacement in SPECIAL_CHARACTERS.items():
            label_content = label_content.replace(char, replacement)

        placeholders = re.findall(PLACEHOLDER_REGEX, label_content)

        for placeholder in placeholders:
            placeholder_attr = placeholder[2:-2]  # Remove %% from start and end
            placeholder_value = FIELD_PLACEHOLDER.format(placeholder_attr)

            label_content = label_content.replace(placeholder, placeholder_value)

        template = TEMPLATE_BASE.format(content=label_content)

        return template

    def _update_label_content(self):
        self.ensure_one()

        # Update label with new content
        self.view_id.arch = self._prepare_label_template()

        # Update action report
        self.action_report_id.name = self.name
        self.action_report_id.print_report_name = self.print_report_name or f"'{self.name}'"

    #
    # Method to call from UI
    #
    @api.model
    def get_label_designer_url(self, label_id=None):
        base_url = self.env['ir.config_parameter'].sudo() \
            .get_param('zpl_label_designer.designer_url')

        if not label_id:
            return f'{base_url}/'

        return f'{base_url}/{label_id}'
