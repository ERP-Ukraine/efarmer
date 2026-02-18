# See LICENSE file for full copyright and licensing details.

from __future__ import absolute_import

from odoo import _
from odoo.api import Environment

from abc import ABCMeta, abstractmethod
from six import with_metaclass

from ..tools import IS_FALSE, is_translated_value, parse_translated_value


class AbsApiClient(with_metaclass(ABCMeta)):

    settings_fields = (
        ('process_order_delay', 'Process order with delay (min)', '0'),
        ('export_template_delay', 'Export template delay (sec)', '0'),
        ('receive_webhook_gap', 'Receive webhook gap (sec)', '60'),
        ('adapter_version', 'Version number of the api client', '0'),
        ('access_granted', 'Access Granted', 'False', True),
    )

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

    def _get_env(self, kw: dict):
        env = kw.get('_env')
        assert isinstance(env, Environment), 'Expected `_env` among key-word arguments'
        return env

    def _get_integration(self, kw: dict):
        env = self._get_env(kw)
        assert self._integration_id, 'Expected assigned `integration_id`'
        return env['sale.integration'].browse(self._integration_id)

    def is_translated_value(self, value):
        return is_translated_value(value)

    def parse_translated_value(self, value, lang=None):
        target_lang = lang or self.lang
        return parse_translated_value(value, target_lang)

    def activate_adapter(self):
        pass

    def order_limit_value(self):
        return 100

    def export_pricelists(self, data):
        raise NotImplementedError('Adapter: export_pricelists')

    def cancel_order(self, *args, **kwargs):
        raise NotImplementedError('Adapter: cancel_order')

    @staticmethod
    def _build_product_external_code(template_id, variant_id=False):
        if template_id is None:
            # Sometimes external stores can return None as product ID. For example:
            # - when product already deleted from the store but was used in the order
            # - when order line is related to specific feature (e.g. Store Credit)
            # Some connectors can handle such cases (Store Credit products), for example, Shopify.
            return None

        if not variant_id:
            return f'{template_id}-{IS_FALSE}'

        return f'{template_id}-{variant_id}'

    @staticmethod
    def _parse_product_external_code(code):
        """
        The external code may be formatted as:
            - (1) False, None, ''
            - (2) "100" (just template)
            - (3) "100-0" (template with the single variant)
            - (4) "100-99" (template with the one of its variants)
        """
        # case (1)
        if not code:
            return code, code

        # case (2)
        if '-' not in code:
            return code, code

        template_id, variant_id = code.rsplit('-', maxsplit=1)

        # case (3)
        if variant_id == IS_FALSE:
            return template_id, template_id

        # case (4)
        return template_id, variant_id

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
    def order_fetch_kwargs(self, *args, **kw):
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
    def export_template_images(self, images_data):
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
    def export_tracking(self, sale_order_id, tracking_data_list, **kw):
        return

    @abstractmethod
    def send_picking(self, sale_order_id, tracking_data, *args, **kw):
        return

    @abstractmethod
    def send_sale_order_status(self, order_id, status):
        return

    @abstractmethod
    def get_product_for_import(self, *args, **kw):
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

    @abstractmethod
    def get_order_url(self, external_order_id):
        """
        Get the order URL for the given external order ID.
        """
        return

    @abstractmethod
    def get_product_url(self, external_product_code):
        """
        Get the product URL for the given external product code.
        """
        return

    @staticmethod
    def _truncate_name_by_dot(field_name, index=-1):
        return field_name.rsplit('.')[index]
