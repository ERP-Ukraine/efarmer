import re

from lxml import etree
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import file_path

# entities disabled and no network access
XML_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)


def element_position(tree, source, path):
    namespaces = {prefix: uri for node in tree.iter(etree.Element) for prefix, uri in node.nsmap.items() if prefix}

    try:
        found = tree.xpath(path, namespaces=namespaces) if path else []
    except etree.XPathError:
        return None

    if not found:
        return None

    element = found[0]
    localname = etree.QName(element).localname
    tag = f'{element.prefix}:{localname}' if element.prefix else localname
    same_tag = [node for node in tree.iter(element.tag) if node.prefix == element.prefix]
    starts = list(re.finditer(rf'<{re.escape(tag)}(?=[\s/>])', source))
    index = same_tag.index(element)

    if index >= len(starts):
        return None

    offset = starts[index].start()
    return source.count('\n', 0, offset) + 1, offset - source.rfind('\n', 0, offset)


class JPKTDocumentType(models.Model):
    _name = 'jpk.document.type'
    _description = 'JPK Document Type'

    name = fields.Char(required=True, size=100)
    active = fields.Boolean(default=True)
    jpk_type = fields.Selection(
        [
            ('JPK', 'JPK - documents sent cyclically'),
            ('JPKAH', 'JPKAH - ad-hoc sending of documents during inspection'),
        ],
        default='JPK',
        required=True,
    )
    system_code = fields.Char(required=True, size=100)
    schema_version = fields.Char(required=True, size=100)
    schema_path = fields.Char()
    description = fields.Text()

    gate_type = fields.Selection(
        [('eDocuments', 'e-Documents'), ('eDeclarations', 'e-Declarations')],
        'API Gate Type',
        default='eDocuments',
    )

    @api.constrains('system_code', 'schema_version', 'name')
    def constrains_unique_values(self):
        for type_id in self:
            # using odoo constrains instead of sql constraints because sql constrains is not removed automatically
            # when removed from odoo, causing problems
            if (
                self.search_count(
                    [('system_code', '=', type_id.system_code), ('schema_version', '=', type_id.schema_version)]
                )
                > 1
            ):
                raise ValidationError(_('System Code & Schema Version must be unique'))

            if self.search_count([('name', '=', type_id.name)]) > 1:
                raise ValidationError(_('Name must be unique'))

    def _get_target_namespace(self):
        self.ensure_one()

        return etree.parse(file_path(self.schema_path), parser=XML_PARSER).getroot().get('targetNamespace')

    @api.model
    def _find_by_namespace(self, namespace):
        for type_id in self.search([('schema_path', '!=', False)]):
            try:
                if type_id._get_target_namespace() == namespace:
                    return type_id
            except (OSError, etree.LxmlError):
                continue

        return self.browse()

    def validate_xml(self, xml_data):
        self.ensure_one()

        errors = []

        if not self.schema_path:
            raise ValidationError(_('Missing XML schema'))

        try:
            schema_tree = etree.parse(file_path(self.schema_path), parser=XML_PARSER)
            xml_schema = etree.XMLSchema(schema_tree)
            target_namespace = schema_tree.getroot().get('targetNamespace')
        except (OSError, etree.LxmlError) as error:
            raise ValidationError(_('Failed to load schema: %s', str(error))) from error

        try:
            if isinstance(xml_data, str):
                xml_data = xml_data.encode()

            # noinspection PyTypeChecker
            source_tree = etree.fromstring(xml_data, parser=XML_PARSER)
            doc_xml = etree.tostring(source_tree, pretty_print=True).decode()
            # noinspection bad-argument-type
            doc_tree = etree.fromstring(doc_xml, parser=XML_PARSER)

        except etree.LxmlError as error:
            raise ValidationError(_('Invalid source xml: %s', str(error))) from error

        if doc_tree is not None and (namespace := etree.QName(doc_tree).namespace) != target_namespace:
            if file_type_id := self._find_by_namespace(namespace):
                raise ValidationError(
                    _(
                        'The file is %(file_type)s, but the document type is %(document_type)s',
                        file_type=file_type_id.name,
                        document_type=self.name,
                    )
                )

            raise ValidationError(
                _(
                    'The file namespace %(namespace)s does not match the document type %(document_type)s',
                    namespace=namespace,
                    document_type=self.name,
                )
            )

        if doc_tree is not None and not xml_schema.validate(doc_tree):
            doc_xml_lines = doc_xml.split('\n')
            source = xml_data.decode('utf-8-sig', errors='replace')

            nsmap = {f'{{{pattern}}}': f'{ns}:' for ns, pattern in schema_tree.getroot().nsmap.items() if ns}

            for error in xml_schema.error_log:
                error_line = doc_xml_lines[error.line - 1].strip()

                message = error.message

                for pattern, ns in nsmap.items():
                    message = message.replace(pattern, ns)

                position = element_position(source_tree, source, error.path)

                errors.append(
                    _(
                        '%(level)s %(message)s\n%(path)s%(position)s: %(line)s',
                        level=error.level_name,
                        message=message,
                        path=error.path,
                        position=f' [{position[0]}:{position[1]}]' if position else '',
                        line=error_line,
                    )
                )

        if errors:
            raise ValidationError('\n\n'.join([_('Errors: %s', len(errors)), *errors]))

        return True
