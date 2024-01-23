# See LICENSE file for full copyright and licensing details.

from odoo.modules import registry
from odoo.tools import lazy_property
from odoo import models

import re


INTEGRATION = 'integration'

STATE_LIST = (
    'installed',
    'to upgrade',
)

SKIP_CLS = {
    'mrp': {
        'False': [
            'odoo.addons.integration.models.mrp_bom.MrpBom',
            'odoo.addons.integration.models.mrp_bom_line.MrpBomLine',
        ],
        'True': [],
    },
    'website_sale': {
        'False': [
            'odoo.addons.integration.models.product_image.ProductImageInherit',
            'odoo.addons.integration.models.product_public_category.ProductPublicCategoryInherit',
        ],
        'True': [
            'odoo.addons.integration.models.product_image.ProductImage',
            'odoo.addons.integration.models.product_public_category.ProductPublicCategory',
        ],
    }
}


def check_module_inheritance(cr, module_name):
    cr.execute('SELECT state FROM ir_module_module WHERE name = %s', (module_name,))
    result = cr.fetchone()
    module_state = result and result[0]
    return module_state and module_state in STATE_LIST


orig_load = registry.Registry.load


def patch_load(reg, cr, module):
    """
    Patch the original `registry.Registry.load` method in order
    to build inheritance of the `mrp.bom`, `mrp.bom.line` models on the fly.
    """
    reg._Registry__cache.clear()
    lazy_property.reset_all(reg)

    skip_cls_list = []

    if module.name == INTEGRATION:
        for module_name, extensions in SKIP_CLS.items():
            skip_cls_list += extensions[str(check_module_inheritance(cr, module_name))]

    model_names = []
    for cls in models.MetaModel.module_to_models.get(module.name, []):
        # str(cls) --> "<class 'odoo.addons.integration.models.mrp_bom.MrpBom'>"
        cls_name = re.findall(r"'(.*?)'", str(cls))
        if cls_name and cls_name[0] in skip_cls_list:
            continue

        model = cls._build_model(reg, cr)
        model_names.append(model._name)

    return reg.descendants(model_names, '_inherit', '_inherits')


registry.Registry.load = patch_load
