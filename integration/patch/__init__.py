# See LICENSE file for full copyright and licensing details.
import re
import logging

import odoo
import odoo.tools as tools

from odoo import models
from odoo.modules.graph import Graph
from odoo.modules.registry import Registry
from odoo.modules.graph import _ignored_modules
from odoo.modules.module import load_openerp_module


_logger = logging.getLogger(__name__)


STATE_LIST = (
    'installed',
    'to upgrade',
)
INTEGRATION = 'integration'
WEBSITE_SALE = 'website_sale'

# We have some models that are inherited from third party modules. We need to
# skip them if the module is not installed.
MODELS_INHERITED_FROM_THIRD_PARTY_MODULES = {
    'website_sale': [
        'odoo.addons.integration.models.product_image.ProductImageInherit',
        'odoo.addons.integration.models.product_public_category.ProductPublicCategoryInherit'
    ],
}

# We also have replacement models for the website_sale module.
# If the module is installed, we need to skip them (and use the original models).
REPLACEMENT_MODELS = {
    'website_sale': [
        'odoo.addons.integration.models.product_image.ProductImage',
        'odoo.addons.integration.models.product_public_category.ProductPublicCategory',
    ]
}


class Module:
    def __init__(self, name):
        self.name = name


def is_module_installed(cr, module_name):
    cr.execute('SELECT state FROM ir_module_module WHERE name = %s', (module_name,))
    result = cr.fetchone()
    module_state = result and result[0]
    return module_state and module_state in STATE_LIST


# Save original methods
Registry._original_load = Registry.load
Graph._original_add_modules = Graph.add_modules


def add_modules_patch(self, cr, module_list, force=None):
    if force is None:
        force = []
    packages = []
    len_graph = len(self)
    for module in module_list:
        info = odoo.modules.module.get_manifest(module)

        if module == INTEGRATION:  # Ventor: patch the `depends` variable
            if is_module_installed(cr, WEBSITE_SALE):
                info['depends'].append(WEBSITE_SALE)

        if info and info['installable']:
            packages.append((module, info))  # TODO directly a dict, like in get_modules_with_version
        elif module not in _ignored_modules(cr):
            _logger.warning('module %s: not installable, skipped', module)

    dependencies = dict([(p, info['depends']) for p, info in packages])
    current, later = set([p for p, info in packages]), set()

    while packages and current > later:
        package, info = packages[0]
        deps = info['depends']

        # if all dependencies of 'package' are already in the graph, add 'package' in the graph
        if all(dep in self for dep in deps):
            if not package in current:
                packages.pop(0)
                continue
            later.clear()
            current.remove(package)
            node = self.add_node(package, info)
            for kind in ('init', 'demo', 'update'):
                if package in tools.config[kind] or 'all' in tools.config[kind] or kind in force:
                    setattr(node, kind, True)
        else:
            later.add(package)
            packages.append((package, info))
        packages.pop(0)

    self.update_from_db(cr)

    for package in later:
        unmet_deps = [p for p in dependencies[package] if p not in self]
        _logger.info('module %s: Unmet dependencies: %s', package, ', '.join(unmet_deps))

    return len(self) - len_graph


def load_patch(reg, cr, module):
    """
    Patch the original `registry.Registry.load` method in order
    to build inheritance of the `mrp.bom`, `mrp.bom.line` models on the fly.
    """
    if module.name != INTEGRATION:
        return reg._original_load(cr, module)

    # Get list of model classes to skip
    classes_to_skip = []

    # Check if the third party modules are not installed
    for module_name, inherited_models in MODELS_INHERITED_FROM_THIRD_PARTY_MODULES.items():
        if not is_module_installed(cr, module_name):
            classes_to_skip += inherited_models

    # Check if the third party modules are installed
    for module_name, replacement_models in REPLACEMENT_MODELS.items():
        if is_module_installed(cr, module_name):
            classes_to_skip += replacement_models

            # Load original module to register original models
            load_openerp_module(module_name)
            reg._original_load(cr, Module(name=module_name))

    # The rest of the code is almost the same as in the original method
    # (with some modifications)

    # Clear cache to ensure consistency, but do not signal it
    for cache in reg._Registry__caches.values():
        cache.clear()

    tools.lazy_property.reset_all(reg)
    reg._field_trigger_trees.clear()
    reg._is_modifying_relations.clear()

    # Instantiate registered classes (via the MetaModel automatic discovery
    # or via explicit constructor call), and add them to the pool.
    model_names = []
    for cls in models.MetaModel.module_to_models.get(module.name, []):
        # str(cls) --> "<class 'odoo.addons.integration.models.mrp_bom.MrpBom'>"
        class_name = re.findall(r"'(.*?)'", str(cls))

        # Skip models that are inherited from the mrp and website_sale modules
        # (if they are not installed)
        if class_name and class_name[0] in classes_to_skip:
            continue

        # Models register themselves in self.models
        model = cls._build_model(reg, cr)
        model_names.append(model._name)

    return reg.descendants(model_names, '_inherit', '_inherits')


Registry.load = load_patch
Graph.add_modules = add_modules_patch
