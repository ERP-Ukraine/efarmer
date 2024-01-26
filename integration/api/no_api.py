# See LICENSE file for full copyright and licensing details.

from __future__ import absolute_import

from odoo import _

from .abstract_apiclient import AbsApiClient


class NoAPIClient(AbsApiClient):
    settings_fields = ()

    def __init__(self, settings):
        super(NoAPIClient, self).__init__(settings)

    def receiveOrders(self, settings):
        raise NotImplementedError()

    def parseOrder(self, settings, raw_order):
        raise NotImplementedError()

    def acknowledgementOrder(self, order):
        raise NotImplementedError()

    def createOrUpdateProducts(self, settings, products, attribute):
        raise NotImplementedError()

    def updateImages(self, settings, products, attribute):
        raise NotImplementedError()

    def getAttributeTypes(self):
        raise NotImplementedError()

    def getAttributes(self):
        raise NotImplementedError()

    def getExternalLinkForOrder(self):
        raise NotImplementedError()

    def check_connection(self):
        return

    def get_api_resources(self):
        return

    def get_delivery_methods(self):
        return

    def get_single_tax(self, tax_id):
        return

    def get_taxes(self):
        return

    def get_payment_methods(self):
        return

    def get_languages(self):
        return

    def get_attributes(self):
        return

    def get_attribute_values(self):
        return

    def get_features(self):
        return

    def get_feature_values(self):
        return

    def get_countries(self):
        return

    def get_states(self):
        return

    def get_categories(self):
        return

    def get_sale_order_statuses(self):
        return

    def get_product_template_ids(self):
        return

    def get_product_templates(self):
        return

    def get_customer_ids(self, date_since=None):
        return

    def get_customer_and_addresses(self, customer_id):
        return

    def receive_orders(self):
        return

    def receive_order(self):
        return

    def parse_order(self, input_file):
        return

    def validate_template(self, template):
        return []

    def find_existing_template(self, template):
        return False

    def export_template(self, template):
        return

    def export_images(self, images):
        return

    def export_attribute(self, attribute):
        return

    def export_attribute_value(self, attribute_value):
        return

    def export_feature(self, feature):
        return

    def export_feature_value(self, feature_value):
        return

    def get_pricelists(self):
        return

    def export_category(self, category):
        return

    def export_inventory(self, inventory):
        return

    def export_tracking(self, sale_order_id, tracking_data_list):
        return

    def export_sale_order_status(self, order_id, status):
        return

    def get_product_for_import(self, product_code, import_images=False):
        return

    def get_templates_and_products_for_validation_test(self, product_refs=None):
        return

    def get_stock_levels(self):
        return

    def get_products_for_accessories(self):
        return

    def create_webhooks_from_routes(self, routes_dict):
        return dict()

    def unlink_existing_webhooks(self, external_ids=None):
        return _('Not Implemented!')

    def _convert_to_html(self, id_list):
        return

    def get_weight_uoms(self):
        return
