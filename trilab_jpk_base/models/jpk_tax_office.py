from lxml import etree

from odoo import fields, models
from odoo.modules import get_resource_path


class JPKTaxOffice(models.Model):
    _name = 'jpk.taxoffice'
    _description = 'JPK Tax Offices'
    _sql_constraints = [('_jpk_tax_office_code_unique_constraint', 'UNIQUE(code)', 'Tax Office code must me unique')]

    name = fields.Char(required=1, size=200, index=True)
    code = fields.Char(required=1, size=10, index=True)

    def load_from_xml(self):
        tree = etree.parse(get_resource_path('trilab_jpk_base', 'data/KodyUrzedowSkarbowych_v4-0E.xsd'))
        ns = {'xsd': 'http://www.w3.org/2001/XMLSchema'}

        self.create(
            [
                {
                    'name': element.find('xsd:annotation/xsd:documentation', namespaces=ns).text,
                    'code': element.attrib['value'],
                }
                for element in tree.xpath(
                    '//xsd:simpleType[@name="TKodUS"]/xsd:restriction/xsd:enumeration', namespaces=ns
                )
            ]
        )
