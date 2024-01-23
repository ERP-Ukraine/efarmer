# See LICENSE file for full copyright and licensing details.

from __future__ import absolute_import

from odoo import _
from odoo.api import Environment

from abc import ABCMeta, abstractmethod
from six import with_metaclass

from ..tools import IS_FALSE


class AbsApiClient(with_metaclass(ABCMeta)):

    def __init__(self, settings):
        super(AbsApiClient, self).__init__()
        self._integration_id = None
        self._integration_name = None
        self._settings = settings

    def __repr__(self):
        return f'<{self.__class__.__name__}({self._integration_id}) at {hex(id(self))}>'

    def get_required_settings_value(self, key):
        value = self.get_settings_value(key)
        if not value:
            raise Exception(f'Setting `{key}` is empty!')
        return value

    def get_settings_value(self, key):
        value = self._settings['fields'][key]['value']
        return value

    def _get_env(self, kw):
        env = kw.get('_env')
        assert isinstance(env, Environment), 'Expected `_env` among key-word arguments'
        return env

    def _get_integration(self, kw):
        env = self._get_env(kw)
        assert self._integration_id, 'Expected assigned `integration_id`'
        return env['sale.integration'].browse(self._integration_id)

    @staticmethod
    def _is_translated_field(value):
        return isinstance(value, dict) and value.get('language')

    def activate_adapter(self):
        pass

    def order_limit_value(self):
        return 100

    def export_pricelists(self, data):
        raise NotImplementedError

    @staticmethod
    def _build_product_external_code(template_id, variant_id=False):
        if not variant_id:
            return f'{template_id}-{IS_FALSE}'
        return f'{template_id}-{variant_id}'

    @staticmethod
    def _parse_product_external_code(code):
        """
        The external code may be formatted as:
            - (1) "100" (just template)
            - (2) "100-0" (template with the single variant)
            - (3) "100-99" (template with the one of its variants)
        """

        # A: handle the (1) case
        if '-' not in code:
            return code, code

        template_id, variant_id = code.rsplit('-', maxsplit=1)

        # B: handle the (2) case
        if variant_id == IS_FALSE:
            return template_id, template_id

        # C: handle the (3) case
        return template_id, variant_id

    @abstractmethod
    def check_connection(self):
        return

    @abstractmethod
    def get_api_resources(self):
        return

    @abstractmethod
    def get_delivery_methods(self):
        return

    @abstractmethod
    def get_single_tax(self, tax_id):
        return

    @abstractmethod
    def get_taxes(self):
        return

    @abstractmethod
    def get_payment_methods(self):
        return

    @abstractmethod
    def get_languages(self):
        return

    @abstractmethod
    def get_attributes(self):
        return

    @abstractmethod
    def get_attribute_values(self):
        return

    @abstractmethod
    def get_features(self):
        return

    @abstractmethod
    def get_feature_values(self):
        return

    @abstractmethod
    def get_countries(self):
        return

    @abstractmethod
    def get_states(self):
        return

    @abstractmethod
    def get_categories(self):
        return

    @abstractmethod
    def get_sale_order_statuses(self):
        return

    @abstractmethod
    def get_product_template_ids(self):
        return

    @abstractmethod
    def get_product_templates(self):
        return

    @abstractmethod
    def get_customer_ids(self, date_since=None):
        return

    @abstractmethod
    def get_customer_and_addresses(self, customer_id):
        return

    @abstractmethod
    def order_fetch_kwargs(*ar, **kw):
        return

    @abstractmethod
    def receive_orders(self):
        """
        Receive orders and prepare input file information

        :return:
        """
        return

    @abstractmethod
    def receive_order(self):
        """
        Receive order and prepare input file information

        :return:
        """
        return

    @abstractmethod
    def parse_order(self, input_file):
        """
        Parse order from input file. Mustn't make any calls to external service

        :param input_file:
        :return:
        """
        return

    @abstractmethod
    def validate_template(self, template):
        """
        Verifies any issues in template. Usually we should verify:
        (1) if template with such external id exists?
        (2) if variant with such external id exists?

        Return format of records to delete:
            [
                {
                        'model': 'product.product',
                        'external_id': <string_external_id> (e.g. '20'),
                },
            [
                {
                        'model': 'product.template',
                        'external_id': <string_external_id> (e.g. '20'),
                },
            ]

        :param template:
        :return: list of mappings to delete
        """
        return []

    @abstractmethod
    def find_existing_template(self, template):
        """
        This method will try to find if there is already existing template
        in external system. And validate that there is correspondence between structure in Odoo
        and in external system (meaning variants and combinations + attributes)

        If product was found, then method will return external_id of the product
        from the external system. So we can import it back as result. Basically should validate:
        (1) If there is only a single product with such reference
        (2) product and all it's variants should have internal reference set
        (3) in case product has variants - it's attributes and attribute values should be the same

        In case any problem found - UserError will be raised with details of the issue

        :param template: serialized template prepared for export to external system
        :return: if of the product in external system (aka. code)
        """
        return False

    @abstractmethod
    def export_template(self, template):
        return

    @abstractmethod
    def export_images(self, images_data):
        """
        :images_data:

        {
            "template": {
                "id": "69",
                "default": {
                    "data": b"...",
                    "mimetype": "image/jpeg",
                    "external_image_id": False,
                    "odoo_obj_name": "product.template",
                    "odoo_obj_id": 9155,
                    "odoo_obj_field_name": "image_1920",
                    "product_name": "presta pro"
                },
                "extra": [
                    {
                        "data": b"...",
                        "mimetype": "image/jpeg",
                        "external_image_id": False,
                        "odoo_obj_name": "product.image",
                        "odoo_obj_id": 2212,
                        "odoo_obj_field_name": "image_1920",
                        "product_name": "presta pro"
                    },
                    {
                        "data": b"...",
                        "mimetype": "image/jpeg",
                        "external_image_id": False,
                        "odoo_obj_name": "product.image",
                        "odoo_obj_id": 2213,
                        "odoo_obj_field_name": "image_1920",
                        "product_name": "presta pro"
                    }
                ],
                "default_code": False
            },
            "products": [
                {
                    "id": "69-179",
                    "default": {
                        "data": b"...",
                        "mimetype": "image/jpeg",
                        "external_image_id": False,
                        "odoo_obj_name": "product.product",
                        "odoo_obj_id": 9261,
                        "odoo_obj_field_name": "image_variant_1920",
                        "product_name": "presta pro"
                    },
                    "extra": [],
                    "default_code": "ppr-1"
                },
                {
                    "id": "69-180",
                    "default": None,
                    "extra": [],
                    "default_code": "ppr-2"
                }
            ]
        }
        """
        return

    @abstractmethod
    def export_attribute(self, attribute):
        return

    @abstractmethod
    def export_attribute_value(self, attribute_value):
        return

    @abstractmethod
    def export_feature(self, feature):
        return

    @abstractmethod
    def export_feature_value(self, feature_value):
        return

    @abstractmethod
    def get_pricelists(self):
        return

    @abstractmethod
    def get_locations(self):
        return

    @abstractmethod
    def export_category(self, category):
        return

    @abstractmethod
    def export_inventory(self, inventory):
        """Send actual QTY to the external services"""
        return

    @abstractmethod
    def export_tracking(self, sale_order_id, tracking_data_list):
        return

    @abstractmethod
    def export_sale_order_status(self, order_id, status):
        return

    @abstractmethod
    def get_product_for_import(self, product_code, import_images=False):
        return

    @abstractmethod
    def get_templates_and_products_for_validation_test(self, product_refs=None):
        """
        product_refs - optional product reference(s) to search duplicates
        It can be either string or single list
        """
        return

    @abstractmethod
    def get_stock_levels(self, *args, **kw):
        return

    @abstractmethod
    def get_products_for_accessories(self):
        return

    def create_webhooks_from_routes(self, routes_dict):
        return dict()

    def unlink_existing_webhooks(self, external_ids=None):
        return _('Not Implemented!')

    @abstractmethod
    def _convert_to_html(self, id_list):
        return

    @abstractmethod
    def get_weight_uoms(self):
        return

    @staticmethod
    def parse_mappings_to_update(variants):
        mappings_to_update = dict()

        variants_ids = {x['id']: x['external_id'] for x in variants}
        variants_ids_values = variants_ids.values()
        if any(variants_ids_values) and not all(variants_ids_values):
            mappings_to_update = {
                x['id']: x['external_id'] for x in variants if x['external_id']
            }
        return mappings_to_update

    @staticmethod
    def _truncate_name_by_dot(field_name, index=-1):
        return field_name.rsplit('.')[index]
