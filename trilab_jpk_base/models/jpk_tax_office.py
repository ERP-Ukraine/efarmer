from lxml import etree
from odoo import fields, models
from odoo.tools import file_path

# latest bundled schema with definitions
TAX_OFFICE_XSD = 'trilab_jpk_base/data/KodyUrzedowSkarbowych_v8-0E.xsd'


class JPKTaxOffice(models.Model):
    _name = 'jpk.taxoffice'
    _description = 'JPK Tax Offices'
    _sql_constraints = [('_jpk_tax_office_code_unique_constraint', 'unique(code)', 'Tax Office code must me unique')]

    name = fields.Char(required=True, size=200, index=True)
    code = fields.Char(required=True, size=10, index=True)

    def load_from_xml(self):
        # loaded from the bundled schema only, no external call to MF servers
        tree = etree.parse(file_path(TAX_OFFICE_XSD))

        ns = {'xsd': 'http://www.w3.org/2001/XMLSchema'}

        self.create(
            [
                {
                    'name': element.find('xsd:annotation/xsd:documentation', namespaces=ns).text,
                    'code': element.attrib['value'],
                }
                for element in tree.xpath(
                    'xsd:simpleType[@name="TKodUS"]/xsd:restriction/xsd:enumeration', namespaces=ns
                )
            ]
        )
