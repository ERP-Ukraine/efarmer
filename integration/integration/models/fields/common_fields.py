# See LICENSE file for full copyright and licensing details.

from odoo import _
from odoo.models import BaseModel
from odoo.exceptions import UserError

from ...tools import normalize_uom_name


BOOLEAN_FIELDS = ['boolean']
FLOAT_FIELDS = ['float', 'monetary']
TEXT_FIELDS = ['char', 'text', 'html']
MANY2ONE_FIELDS = ['many2one']

GENERAL_GROUP = 'general_group'


class CommonFields:

    def __init__(self, integration, odoo_obj, external_obj):
        self.integration = integration.sudo()
        self.external_obj = external_obj
        self.env = self.integration.env

        record = odoo_obj
        if isinstance(odoo_obj, BaseModel):
            record = odoo_obj.sudo()

            if self.integration:
                record = record.with_context(
                    lang=self.integration.get_integration_lang_code(),
                )

        self.odoo_obj = record

    def __repr__(self):
        name = f'{self.__class__.__name__}({self.integration.id})'
        return f'<{name} at {hex(id(self))}: {self.odoo_obj}>'

    @property
    def adapter(self):
        return self.integration._build_adapter()

    @property
    def is_template(self):
        return self.odoo_obj._name == 'product.template'

    @property
    def is_variant(self):
        return self.odoo_obj._name == 'product.product'

    def calculate_field_value(self, ecommerce_field):
        converter_method = getattr(self, '_get_{}_value'.format(ecommerce_field.value_converter))
        if not converter_method:
            raise UserError(
                _(
                    'There is no method defined for converter %s'
                ) % ecommerce_field.value_converter
            )
        return converter_method(ecommerce_field)

    def _get_ecommerce_fields_mapping(self, domain_ext):
        xml_id = 'product.model_%s' % '_'.join(self.odoo_obj._name.split('.'))

        search_domain = [
            ('integration_id', '=', self.integration.id),
            ('odoo_model_id', '=', self.env.ref(xml_id).id),
        ]
        if domain_ext:
            search_domain += domain_ext

        return self.env['product.ecommerce.field.mapping'].search(search_domain)\
            .mapped('ecommerce_field_id')

    def _get_ecommerce_field(self, field_name):
        xml_id = 'product.model_%s' % '_'.join(self.odoo_obj._name.split('.'))

        search_domain = [
            ('odoo_field_id.name', '=', field_name),
            ('odoo_model_id', '=', self.env.ref(xml_id).id),
            ('type_api', '=', self.integration.type_api),
        ]
        return self.env['product.ecommerce.field'].sudo().search(search_domain)

    def calculate_fields(self, domain_ext):
        vals = {}

        for field in self._get_ecommerce_fields_mapping(domain_ext):
            field_values = self.calculate_field_value(field)
            vals = self._update_calculated_fields(vals, field_values)

        return vals

    def _update_calculated_fields(self, vals, field_values):
        vals.update(field_values)
        return vals

    def _compute_field_value_using_python_method(self, method_name, field_name):
        # Check method declares in converter class
        python_method = getattr(self, method_name, None)
        if python_method:
            return python_method(field_name)

        # If thera is not method in converter class, check it in
        # product.product or product.template
        # It's made for users who use own method for generating values
        python_method = getattr(self.odoo_obj, method_name, None)
        if python_method:
            return python_method(self.integration, field_name)

        raise UserError(
            _(
                'There is no method %s defined for object %s'
            ) % (method_name, self.odoo_obj._name)
        )

    def _check_combinations_not_exist(self, odoo_template):
        variants = odoo_template.product_variant_ids

        if len(variants) == 1:
            external_record = variants.try_to_external_record(self.integration)
            product_code = external_record and external_record.code

            if not product_code or product_code.split('-')[1] == '0':
                return True

        return False

    def _convert_weight_uom(self, weight, uom_name, is_import):
        """
            This method try to find unit of weight measure by name from e-Commerce System
            and convert it
        """
        if not uom_name:
            return weight

        uom_name = normalize_uom_name(uom_name)

        external_weight_uom = self.env['uom.uom'].search([
            ('category_id', '=', self.env.ref('uom.product_uom_categ_kgm').id),
            ('name', '=ilike', uom_name),
        ], limit=1)

        if not external_weight_uom:
            raise UserError(_(
                'Odoo does not have a unit of weight measure with the name "%s" defined. '
                'Please, go to "Sales->Settings->Units of Measure Categories->Weight" '
                'and create it.') % uom_name)

        odoo_weight_uom = self.env["product.template"]._get_weight_uom_id_from_ir_config_parameter()

        if external_weight_uom != odoo_weight_uom:
            if is_import:
                weight = external_weight_uom._compute_quantity(weight, odoo_weight_uom)
            else:
                weight = odoo_weight_uom._compute_quantity(weight, external_weight_uom)

        return weight
