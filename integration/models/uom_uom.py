# See LICENSE file for full copyright and licensing details.

from odoo import api, models, _
from odoo.exceptions import UserError

from ..tools import normalize_uom_name


class UomUom(models.Model):
    _inherit = 'uom.uom'

    @api.model
    def _convert_external_weight_uom(self, weight: float, external_uom_name: str, is_import: bool = True):
        """
        This method try to find unit of weight measure by name from e-Commerce System
        and convert it
        """
        if not weight:
            return 0

        if not external_uom_name:
            return weight

        external_weight_uom = self.env['uom.uom'].search([
            ('name', '=ilike', normalize_uom_name(external_uom_name)),
        ], limit=1)

        if not external_weight_uom:
            raise UserError(_(
                'Odoo does not have a unit of weight measure with the name "%s" defined. '
                'Please go to "Sales → Settings → Units of Measure Categories → Weight" '
                'and create this unit of measure to continue.'
            ) % normalize_uom_name(external_uom_name))

        odoo_weight_uom = self.env['product.template']._get_weight_uom_id_from_ir_config_parameter()

        if external_weight_uom != odoo_weight_uom:
            if is_import:
                weight = external_weight_uom._compute_quantity(weight, odoo_weight_uom)
            else:
                weight = odoo_weight_uom._compute_quantity(weight, external_weight_uom)

        return weight
