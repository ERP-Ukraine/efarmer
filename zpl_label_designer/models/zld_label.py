import ast
import re
import string

from lxml import etree
from typing import Any, Dict, List, Union

from odoo import api, exceptions, fields, models, _
from odoo.tools.safe_eval import safe_eval, test_python_expr, time


LABEL_VIEW_XMLID = 'zpl_label_designer.{model}_label_{label_id}'
LABEL_ACTION_REPORT_XMLID = 'zpl_label_designer.{model}_label_action_{label_id}'
FORMULA_PREFIX = 'FORMULA:'
FORMULA_DOC_FIELD_REGEX = re.compile(r'\bdoc\.([a-zA-Z_][a-zA-Z0-9_]*)')
FORMULA_ATTRIBUTE_REGEX = re.compile(r'doc\._get_attribute\(\s*[\'"]([^\'"]+)[\'"]\s*\)')
FORMULA_ALLOWED_MODEL_METHODS = {
    'product.product': {
        '_get_attribute',
    },
    'product.template': {
        '_get_attribute',
    },
}
# What formulas and template expressions can't reach: other models, raw SQL, the rights of
# other users and writes. safe_eval allows all of it and only the environment limits it
EXPRESSION_FORBIDDEN_NAMES = {'env', 'request'}
EXPRESSION_FORBIDDEN_ATTRIBUTES = {
    'cr', 'env', 'pool', 'registry', 'sudo', 'with_env', 'with_user',
    'copy', 'create', 'unlink', 'write',
    'action_archive', 'action_unarchive', 'copy_translations', 'load', 'name_create', 'toggle_active', 'update',
    'update_field_translations', 'web_override_translations', 'web_resequence', 'web_save', 'web_save_multi',
    'web_unlink',
    'format_map',
}
EXPRESSION_ALLOWED_PRIVATE_ATTRIBUTES = set().union(*FORMULA_ALLOWED_MODEL_METHODS.values())
# The directives a label template can use, all others are refused. t-set holds an expression too:
# QWeb reads a dictionary from it
TEMPLATE_NAME_DIRECTIVES = {'t-as', 't-name'}
TEMPLATE_EXPRESSION_DIRECTIVES = {
    't-att', 't-elif', 't-else', 't-esc', 't-field', 't-foreach', 't-if', 't-options', 't-out', 't-raw', 't-set',
    't-value',
}
TEMPLATE_EXPRESSION_PREFIXES = ('t-att-', 't-options-')
TEMPLATE_FORMAT_DIRECTIVES = {'t-valuef'}
TEMPLATE_FORMAT_PREFIX = 't-attf-'
TEMPLATE_TRANSLATE_SUFFIX = '.translate'
# The same as in QWeb, without re.DOTALL: another split would hide an expression from the check
TEMPLATE_FORMAT_REGEX = re.compile(r'\{\{(.+?)\}\}|#\{(.+?)\}')
# What the designer API can set on a label. The rest, such as the related view, is managed by the module
LABEL_API_FIELDS = ('name', 'width', 'height', 'dpi', 'orientation', 'designer_label_id')


class _ReadOnlyCallDone(Exception):
    """Leaves the savepoint of a read-only call: rolling it back restores writing."""


class Label(models.Model):
    _name = 'zld.label'
    _description = 'ZPL Designer Label'

    # Some fields below are part of the Ventor PRO API contract,
    # see tests/test_ventor_api_contract.py for details

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

    dpi = fields.Float(
        string="DPI",
        required=True,
        readonly=True,
    )

    orientation = fields.Selection(
        default="normal",
        selection=[('normal', 'Normal'), ('inverted', 'Inverted')],
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

    convert_to_pdf = fields.Boolean(
        string='Convert Label to PDF',
        default=False,
        help=(
            'If enabled, the label will be converted to PDF format using Labelary API when printing or downloading. '
            'If disabled, the original ZPL format will be returned (default Odoo behavior).'
        ),
    )

    @api.depends('name', 'print_report_name')
    def _compute_print_report_name_preview(self):
        for rec in self:
            if not rec.print_report_name:
                rec.print_report_name_preview = rec.name
                continue

            try:
                rec._check_expression(rec.print_report_name)
            except exceptions.UserError:
                # An error here would keep the form of a label saved earlier from opening
                rec.print_report_name_preview = _('Expression is not allowed')
                continue

            random_record = rec.env[rec.model_id.model].search([], limit=1)
            rec.print_report_name_preview = safe_eval(
                rec.print_report_name,
                {'object': random_record}
            )

    @api.onchange('print_report_name')
    def _onchange_print_report_name(self):
        if self.print_report_name:
            # Check if expression is valid
            try:
                self._check_expression(self.print_report_name)
                self._compute_print_report_name_preview()
            except Exception as e:
                raise exceptions.ValidationError(
                    _('Invalid Print Report Name expression: {}').format(e)
                )

    @api.constrains('print_report_name')
    def _check_print_report_name(self):
        """
        Reject report name expressions that do more than read and format values of the record.

        The expression runs with the rights of whoever opens the label or downloads its report.
        Without this check a label manager could make an administrator run any code just by
        getting them to open the label.
        """
        for rec in self.filtered('print_report_name'):
            rec._check_expression(rec.print_report_name)

    def copy(self, default=None):
        raise exceptions.UserError(_(
            "You can't duplicate a label. Please, go to the Label Designer PRO to create labels."
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
        Create or update report and view for label
        """
        self.ensure_one()

        if not self.view_id:
            raise exceptions.UserError(_(
                'To publish this label, please go to the Designer (using "Open in Designer" button)'
                ' and publish it there'
            ))

        self.view_id.active = True

        if self.action_report_id:
            # Update action report
            self.action_report_id.name = self.name
            self.action_report_id.print_report_name = self.print_report_name or repr(self.name)
        else:
            # Create action report
            self.action_report_id = self._create_label_action_report()

        self.is_published = True

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Label was published'),
                'message': _('Label {} was successfully published').format(self.name),
                'type': 'success',
                'sticky': False,
                'next': {  # Refresh the page after publishing
                    'type': 'ir.actions.client',
                    'tag': 'reload',
                }
            },
        }

    def unpublish(self):
        self.ensure_one()

        if self.action_report_id:
            self.action_report_id.unlink()
            self.view_id.active = False

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

    #
    # Methods of the designer API. Private so they can't be called over RPC: they evaluate
    # expressions from the request, and the controllers are the only callers
    #
    @api.model
    def _create_label(self, attrs):
        qweb_xml, label_fields, prepared_attrs = self._prepare_data_for_label(attrs)

        label = self.create([prepared_attrs])
        label._publish_label(qweb_xml)
        label._update_preview(label_fields)

        return label.id

    @api.model
    def _update_label(self, label_id, attrs):
        # Use exists to make sure that label really exists
        label = self.browse(label_id).exists()

        if not label:
            # Create new label if it doesn't exist
            label_id = self._create_label(attrs)
            return label_id

        qweb_xml, label_fields, prepared_attrs = self._prepare_data_for_label(attrs)

        label.write(prepared_attrs)
        label.view_id.arch = qweb_xml
        label._update_preview(label_fields)

        return label.id

    @api.model
    def _delete_label(self, label_id):
        label = self.browse(label_id).exists()

        if not label:
            # TODO: Maybe it's better just to return success?
            raise ValueError(_('Not label with such ID found in Odoo'))

        # This will raise exception if label published
        label.unlink()

    @api.model
    def _get_preview_data(self, model_name, fields):
        """
        Returns example of data to populate label for preview
        """
        self._check_formula_support(fields)

        # Validate fields
        self._validate_label_fields(model_name, fields)

        # Try to find objects with not empty fields
        random_record = self._get_random_record(model_name, fields)

        # Example of fields: [{"order_line": ["product_id.name", "product_uom_qty"]}, "state"]
        # We need to leave only fields that are in fields list
        data = self._call_read_only(self._get_data_from_record, random_record, fields)

        return data

    #
    # Internal methods
    #
    def _update_preview(self, label_fields: Dict[str, Union[None, List[Any], Dict[str, Any]]]):
        """
        Generate label preview from Qweb template based on random record
        """
        random_record_id = self._get_random_record(self.model_id.model, label_fields)

        try:
            preview = self._call_read_only(self._render_qweb_text, [random_record_id.id]).decode('utf-8')
        except Exception:
            if random_record_id:
                raise

            # The model has no records yet and the label can't be rendered without data
            # (e.g. its formulas need a record), so the label is saved without the preview
            preview = False

        self.preview = preview

    def _call_read_only(self, function, *args):
        """
        Call a function that evaluates label expressions so that they can't change data, even
        though the designer API runs them as the superuser.

        :param function: function to call
        :return: result of the function
        """
        result = None

        try:
            with self.env.cr.savepoint():
                self.env.cr.execute('SET LOCAL transaction_read_only = on')
                result = function(*args)
                raise _ReadOnlyCallDone()
        except _ReadOnlyCallDone:
            pass

        return result

    def _publish_label(self, qweb_xml: str):
        """ Internal method to create report and view for label
        """
        label_view_id = self._create_label_view(qweb_xml)

        self.view_id = label_view_id

        label_action_report = self._create_label_action_report()

        self.action_report_id = label_action_report
        self.is_published = True

    def _get_random_record(self, model_name: str, fields: Dict[str, Union[None, List[Any], Dict[str, Any]]]):  # NOQA
        """
        This method returns random record from model
        (tries to find record with fields that are not empty).
        Returns an empty recordset if the model has no records.
        """
        Model = self.env[model_name]
        domain = self._get_preview_domain(Model, fields)
        random_record = Model.search(domain, limit=1)

        if not random_record:
            # If no object found, try to find any object
            random_record = Model.search([], limit=1)

        return random_record

    def _create_label_view(self, view_content: str):
        """ This method creates view for current label
        """
        self.ensure_one()

        view_xmlid = LABEL_VIEW_XMLID.format(
            model=self.model_id.model.replace(".", "_"), label_id=self.id)

        label_view_id = self.env['ir.ui.view'].create({
            'type': 'qweb',
            'arch': view_content,
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

        return label_view_id

    def _create_label_action_report(self):
        """ This method creates actions report for current label
        """
        self.ensure_one()

        action_xmlid = LABEL_ACTION_REPORT_XMLID.format(
            model=self.model_id.model.replace(".", "_"), label_id=self.id)

        view_xmlid = self.view_id.get_external_id()[self.view_id.id]

        if not view_xmlid:
            raise exceptions.UserError(_(
                "View have not been created for the label - have not view - it's not possible to "
                "create an action report for this label."
            ))

        label_action_report = self.env['ir.actions.report'].create({
            'xml_id': action_xmlid,
            'name': self.name,
            'model': self.model_id.model,
            'report_type': 'qweb-text',
            'report_name': view_xmlid,
            'report_file': view_xmlid,
            'print_report_name': self.print_report_name or repr(self.name),
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

        return label_action_report

    def _prepare_data_for_label(self, attrs):
        """ Prepare attributes to create (update) label
        """
        qweb_xml = attrs.pop('qweb_xml', None)
        if not qweb_xml:
            raise exceptions.UserError(
                _('Label is empty. Please add at least one element to the label'))

        model_name = attrs.pop('model', None)
        if not model_name:
            raise exceptions.UserError(_('Model is not specified'))

        prepared_attrs = {field: attrs[field] for field in LABEL_API_FIELDS if field in attrs}

        # Replace model with model_id. It's a bit hacky but for now it's the easiest way
        prepared_attrs['model_id'] = self.env['ir.model'].search([('model', '=', model_name)]).id

        label_fields = attrs.pop('label_fields', None)

        self._check_formula_support(label_fields)
        self._validate_label_fields(model_name, label_fields)
        self._check_template_expressions(qweb_xml)

        return qweb_xml, label_fields, prepared_attrs

    def _render_qweb_text(self, docids: list):
        """
        Render Qweb template to text
        """
        self.ensure_one()

        docs = self.env[self.model_id.model].browse(docids)
        view_xmlid = self.view_id.get_external_id()[self.view_id.id]
        data = {
            'doc_ids': docids,
            'doc_model': self.model_id.model,
            'docs': docs,
            'zld_label': self,
        }
        return self.env['ir.actions.report'] \
            .with_context(minimal_qcontext=True) \
            ._render_template(view_xmlid, data)

    def get_barcode_offset(self, *, text, width, align, barcode_size):
        """
        Return the Code 128 offset along the barcode direction within its Konva field.

        The portal resolves the field geometry (rotation, axis, align) when it publishes
        the label; only the barcode width depends on the record value.

        :param align: 'start', 'center' or 'end' along the barcode direction
        """
        self.ensure_one()

        # Code 128 consists of:
        # - start symbol: 11 modules
        # - data symbols: 11 modules each
        # - checksum symbol: 11 modules
        # - stop symbol: 13 modules
        #
        # `len(text) + 2` represents data symbols + start + checksum.
        # Multiply the total number of modules by barcode_size (^BY module width)
        # to get the actual barcode width in printer dots.
        #
        # The formula holds while the portal generates ^BC without the mode parameter
        # (one symbol per character, Subset B) and the value has no ZPL invocation codes (">").
        barcode_width = (11 * (len(str(text)) + 2) + 13) * barcode_size

        # Do not shift a barcode that is wider than the Konva field
        free_width = max(width - barcode_width, 0)

        if align == 'start':
            return 0
        if align == 'end':
            return free_width
        return free_width // 2

    @classmethod
    def _get_data_from_record(cls, random_record, fields: Dict[str, Union[None, List[Any], Dict[str, Any]]]):  # NOQA
        """
        Recursive method to get fields values from record
        """
        data = {}

        for field, subfields in fields.items():
            if cls._is_formula_field(field):
                # Formula field, for example: FORMULA:doc.name[:5]
                data[field] = cls._get_formula_value(random_record, field)
            elif subfields is None:
                # Simple field
                data[field] = getattr(random_record, field)
            elif isinstance(subfields, dict):
                # Dict means that the field is many2one field
                data[field] = cls._get_data_from_record(getattr(random_record, field), subfields)
            elif isinstance(subfields, list):
                # List means that the field is many2many or one2many field
                data[field] = []

                for record in getattr(random_record, field):
                    data[field].append(cls._get_data_from_record(record, subfields[0]))
            else:
                raise ValueError('Something is wrong with used fields')

        return data

    @api.model
    def _validate_label_fields(self, model_name: str, fields: Dict[str, Union[None, List[Any], Dict[str, Any]]]):  # NOQA
        """
        Recursive method to validate existance of specified fields
        """
        Model = self.env[model_name]
        model_label = Model._description

        for field, subfields in fields.items():
            if self._is_formula_field(field):
                # Formula field, for example: FORMULA:doc.name[:5]
                if subfields is not None:
                    raise ValueError('Formula field should not have subfields')

                formula_expression = self._get_formula_expression(field)
                error = test_python_expr(formula_expression, mode='eval')
                if error:
                    raise exceptions.UserError(
                        _("Formula '{}' is invalid: {}").format(formula_expression, error)
                    )

                self._check_expression(formula_expression)

                formula_fields = self._get_formula_field_names(field)
                if not formula_fields:
                    raise exceptions.UserError(
                        _("Formula '{}' does not contain doc fields").format(formula_expression)
                    )

                allowed_methods = FORMULA_ALLOWED_MODEL_METHODS.get(model_name, set())

                for formula_field in formula_fields:
                    # Check if the formula_field uses an existing Odoo field
                    if formula_field in Model._fields:
                        continue

                    # Check if the formula_field uses an allowed model method
                    if formula_field in allowed_methods and callable(getattr(Model, formula_field, None)):
                        continue

                    raise exceptions.UserError(
                        _(
                            "'{}' is not a field of model '{}' ({}) and is not an allowed method"
                        ).format(formula_field, model_label, model_name)
                    )

                continue

            if field not in Model._fields:
                    raise exceptions.UserError(
                        _("Field '{}' does not exist in model '{}' ({})").format(field, model_label, model_name)  # NOQA
                    )

            if subfields is None:
                # Simple field, checked above
                pass
            elif isinstance(subfields, dict):
                # Dict means that the field is many2one field
                if Model._fields[field].type != 'many2one':
                    raise exceptions.UserError(
                        _("Field '{}' is not many2one field in model '{}' ({})").format(field, model_label, model_name)  # NOQA
                    )

                self._validate_label_fields(Model._fields[field].comodel_name, subfields)
            elif isinstance(subfields, list):
                # List means that the field is many2many or one2many field
                if Model._fields[field].type not in ('many2many', 'one2many'):
                    raise exceptions.UserError(
                        _("Field '{}' is not many2many or one2many field in model '{}' ({})").format(field, model_label, model_name)  # NOQA
                    )

                self._validate_label_fields(Model._fields[field].comodel_name, subfields[0])
            else:
                raise ValueError('Something is wrong with used fields')

    @api.model
    def _check_template_expressions(self, qweb_xml):
        """
        Check every expression of a template: QWeb renders the template as it is, whatever
        the label fields declare.
        """
        for node in etree.fromstring(qweb_xml.encode()).iter():
            for directive, value in node.attrib.items():
                for expression in self._get_directive_expressions(directive, value):
                    self._check_expression(expression)

    @api.model
    def _get_directive_expressions(self, directive, value):
        """
        Get Python expressions from the value of a template attribute.

        An unknown directive is refused: QWeb compiles attributes to code in ways that differ
        between Odoo versions, so what it does with such a directive can't be checked.
        """
        if not directive.startswith('t-'):
            return []

        if directive.endswith(TEMPLATE_TRANSLATE_SUFFIX):
            directive = directive[:-len(TEMPLATE_TRANSLATE_SUFFIX)]

        if directive in TEMPLATE_NAME_DIRECTIVES:
            return []

        if directive in TEMPLATE_FORMAT_DIRECTIVES or directive.startswith(TEMPLATE_FORMAT_PREFIX):
            return [first or second for first, second in TEMPLATE_FORMAT_REGEX.findall(value)]

        if directive in TEMPLATE_EXPRESSION_DIRECTIVES or directive.startswith(TEMPLATE_EXPRESSION_PREFIXES):
            return [value] if value.strip() else []

        raise exceptions.UserError(_(
            "Templates can't use '{}'. Labels can only read and format values of the record."
        ).format(directive))

    @api.model
    def _check_expression(self, expression):
        """
        Raise an error if an expression does more than read and format values of the record.

        Expressions come from the designer, not from an administrator, and run as the superuser
        or as whoever prints the label. safe_eval and QWeb don't limit what they do with the ORM.
        """
        try:
            tree = ast.parse(expression.strip(), mode='eval')
        except (SyntaxError, ValueError) as e:
            raise exceptions.UserError(_("Expression '{}' is invalid: {}").format(expression, e))

        for node in ast.walk(tree):
            forbidden = None

            if isinstance(node, ast.Name) and node.id in EXPRESSION_FORBIDDEN_NAMES:
                forbidden = node.id
            elif isinstance(node, ast.Attribute) and self._is_forbidden_attribute(node):
                forbidden = node.attr

            if forbidden:
                raise exceptions.UserError(_(
                    "Expression '{}' can't use '{}'. Labels can only read and format values of the record."
                ).format(expression, forbidden))

    @classmethod
    def _is_forbidden_attribute(cls, node):
        """
        Check if an attribute of an expression can't be used.
        """
        if node.attr == 'format':
            return not cls._is_plain_format_string(node.value)

        if node.attr.startswith('_'):
            return node.attr not in EXPRESSION_ALLOWED_PRIVATE_ATTRIBUTES

        return node.attr in EXPRESSION_FORBIDDEN_ATTRIBUTES

    @staticmethod
    def _is_plain_format_string(node):
        """
        Check if a node is a format string that reads no attributes: '{0.env}'.format(doc) reads
        them from a string, where the names of an expression can't be checked.
        """
        # ast.Constant keeps the text in value, ast.Str of Python 3.7 in s
        value = node.value if hasattr(node, 'value') else getattr(node, 's', None)
        if not isinstance(value, str):
            return False

        try:
            parts = list(string.Formatter().parse(value))
        except ValueError:
            return False

        for _literal, field, spec, _conversion in parts:
            if '.' in (field or '') or '[' in (field or '') or '{' in (spec or ''):
                return False

        return True

    @staticmethod
    def _is_formula_field(field):
        """
        Check if field is a formula expression.
        """
        return isinstance(field, str) and field.startswith(FORMULA_PREFIX)

    @classmethod
    def _has_formula_fields(cls, label_fields):
        """
        Check if label fields use a formula at any depth: a formula of a related record runs
        the same way, so it must not get past the Enable Formulas setting.
        """
        for field, subfields in label_fields.items():
            if cls._is_formula_field(field):
                return True

            if isinstance(subfields, list) and subfields:
                subfields = subfields[0]

            if isinstance(subfields, dict) and cls._has_formula_fields(subfields):
                return True

        return False

    @classmethod
    def _get_formula_expression(cls, formula):
        """
        Get formula expression without technical prefix.
        Example:
            FORMULA:doc.name[:5]
            -> doc.name[:5]
        """
        if cls._is_formula_field(formula):
            return formula[len(FORMULA_PREFIX):]

        return formula

    @classmethod
    def _get_formula_field_names(cls, formula):
        """
        Get field names used in formula expression.
        """
        formula = cls._get_formula_expression(formula)
        return list(dict.fromkeys(FORMULA_DOC_FIELD_REGEX.findall(formula)))

    @classmethod
    def _get_domain_field_names(cls, Model, fields):
        """
        Get field names to use in search domain.
        Non-stored fields are excluded because Odoo builds SQL queries in to_sql()
        for search, and non-stored fields (store=False) do not exist in the database.

        Example:
            {
                "FORMULA:doc.name[:5]": None,
                "hs_code": None,
            }
            -> ["name", "hs_code"]
        """
        field_names = []

        for field in fields.keys():
            if cls._is_formula_field(field):
                field_names.extend(cls._get_formula_field_names(field))
            else:
                field_names.append(field)

        result = []
        for f in dict.fromkeys(field_names):
            model_field = Model._fields.get(f)
            if model_field and model_field.store and model_field.column_type:
                result.append(f)

        return result

    @classmethod
    def _get_product_attribute_domain(cls, Model, fields):
        """
        Get search domain for product attributes passed to _get_attribute()
        in formula expressions. Attribute names are searched in any installed language.
        """
        if Model._name not in ('product.product', 'product.template'):
            return []

        attribute_names = []

        for field in fields.keys():
            if not cls._is_formula_field(field):
                continue

            formula = cls._get_formula_expression(field)
            attribute_names.extend(
                FORMULA_ATTRIBUTE_REGEX.findall(formula)
            )

        if not attribute_names:
            return []

        attribute_names = list(dict.fromkeys(attribute_names))
        attributes_by_name = Model.env['product.attribute']._search_by_names(attribute_names)

        domain = []

        for attribute_name in attribute_names:
            attributes = attributes_by_name.get(attribute_name)

            if not attributes:
                continue

            # Template attribute lines contain attributes that don't create variants as well
            domain.append((
                'attribute_line_ids.attribute_id',
                'in',
                attributes.ids,
            ))

        return domain

    @classmethod
    def _get_preview_domain(cls, Model, fields):
        """
        Get search domain for selecting a preview record
        with non-empty fields and required product attributes.
        """
        field_names = cls._get_domain_field_names(Model, fields)

        domain = [
            (field_name, '!=', False)
            for field_name in field_names
        ]

        domain.extend(cls._get_product_attribute_domain(Model, fields))

        return domain

    @classmethod
    def _get_formula_value(cls, random_record, formula):
        """
        Evaluate formula using random record and return result as string.

        Example:
            random_record.name = "Acoustic Bloc Screens"
            formula = "FORMULA:doc.name[:5]"
            result = "Acous"
        """
        formula_expression = cls._get_formula_expression(formula)

        try:
            value = safe_eval(formula_expression, {'doc': random_record, 'time': time})
        except Exception as e:
            if not random_record:
                # There is no record to evaluate the formula on: the model has no records yet
                # or the many2one field used in the label is empty
                return ''

            raise exceptions.UserError(
                _("Formula '{}' cannot be evaluated: {}").format(formula_expression, e)
            )

        if value is False or value is None:
            return ''

        if isinstance(value, models.BaseModel):
            return value.display_name

        return str(value)

    @api.model
    def _check_formula_support(self, label_fields):
        """
        Raise an error if the label uses formulas while formula support is disabled.
        Formula fields are stored as keys that start with 'FORMULA:', for example:
            {
                "FORMULA:doc.name[:5]": None,
                "hs_code": None,
            }
        """
        if not label_fields:
            return

        if self._has_formula_fields(label_fields) and not self.env.company.sudo().enable_formulas:
            raise exceptions.UserError(_(
                "This label contains formulas, but formula support is currently disabled.\n\n"
                "Please enable formula support in the Label Designer PRO settings in Odoo."
            ))

    #
    # Method to call from UI
    #
    @api.model
    def get_label_designer_url(self, label_id: str = None):
        base_url = self.env['ir.config_parameter'].sudo() \
            .get_param('zpl_label_designer.designer_url')

        if not label_id:
            return f'{base_url}/labels'

        return f'{base_url}/{label_id}'
