# Inherited from the `integration.external.mixin`
from . import integration_delivery_carrier_external
from . import integration_account_tax_external
from . import integration_account_tax_group_external
from . import integration_sale_order_payment_method_external
from . import integration_product_attribute_external
from . import integration_product_attribute_value_external
from . import integration_res_lang_external
from . import integration_res_partner_external
from . import integration_res_country_external
from . import integration_res_country_state_external
from . import integration_product_template_external
from . import integration_product_product_external
from . import integration_product_public_category_external
from . import integration_sale_order_external
from . import integration_sale_order_sub_status_external
from . import integration_product_pricelist_external
from . import integration_stock_location_external

# Not inherits `integration.external.mixin`
from . import external_order_resource
from . import integration_product_pricelist_item_external
from . import external_stock_location_line
from . import external_integration_tag
from . import external_order_transaction
from . import external_order_fulfillment_line
from . import external_order_fulfillment
from . import integration_product_image_external

# Models required for Odoo 19.0 migration
from . import integration_ecommerce_product_category_external
