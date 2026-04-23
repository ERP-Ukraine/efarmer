import requests
from lxml import etree
from odoo import fields, models
from odoo.tools import file_path

# noinspection HttpUrlsUsage
MF_TAX_OFFICE_URL = (
    'http://crd.gov.pl/xml/schematy/dziedzinowe/mf/2016/01/25/eD/DefinicjeTypy/KodyUrzedowSkarbowych_v4-0E.xsd'
)


class JPKTaxOffice(models.Model):
    _name = 'jpk.taxoffice'
    _description = 'JPK Tax Offices'
    _sql_constraints = [('_jpk_tax_office_code_unique_constraint', 'unique(code)', 'Tax Office code must me unique')]

    name = fields.Char(required=True, size=200, index=True)
    code = fields.Char(required=True, size=10, index=True)

    def load_from_xml(self):
        try:
            response = requests.get(MF_TAX_OFFICE_URL)
            response.raise_for_status()
            tree = etree.fromstring(response.content)
        except requests.RequestException:
            tree = etree.parse(file_path('trilab_jpk_base/data/KodyUrzedowSkarbowych_v4-0E.xsd'))

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
