# See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError
from odoo import models, fields, _

from ..exceptions import NotMappedToExternal


class RefreshProductsWizard(models.TransientModel):
    _name = 'refresh.products.wizard'
    _description = 'Refresh from Store'

    template_ids = fields.Many2many(
        comodel_name='product.template',
        string='Products',
    )
    allowed_integration_ids = fields.Many2many(
        comodel_name='sale.integration',
        string='Allowed E-Commerce Stores',
    )
    allowed_integration_count = fields.Integer(
        string='Allowed E-Commerce Stores Count',
    )
    integration_id = fields.Many2one(
        string='Refresh from E-Commerce Store',
        comodel_name='sale.integration',
        domain="[('id', 'in', allowed_integration_ids)]",
        required=True,
    )
    export_to_other = fields.Boolean(
        string='Export Product Info to Other E-Commerce Systems',
        help='As the Product is connected to other sales channels except selected in '
             '“Refresh from Integration“ above, you can automatically export product '
             'information to other integrations just after you refresh it. '
    )

    def default_get(self, fields_list):
        values = super(RefreshProductsWizard, self).default_get(fields_list)

        template_ids = self.env.context.get('template_ids')
        allowed_integration_ids = self.env.context.get('allowed_integration_ids', [])
        integration_count = len(allowed_integration_ids)

        values['template_ids'] = [(6, 0, template_ids)]
        values['allowed_integration_ids'] = [(6, 0, allowed_integration_ids)]
        values['integration_id'] = integration_count == 1 and allowed_integration_ids[0] or False
        values['allowed_integration_count'] = integration_count

        return values

    def run_refresh(self):
        for template in self.template_ids:
            try :
                external_template = template.to_external_record(self.integration_id)
            except NotMappedToExternal:
                raise UserError(_(
                    'Product "%s" does not have a mapping with the E-Commerce System "%s", '
                    'so external product for refreshing can\'t be found.\n\n'
                    'Please ensure the product is correctly mapped before proceeding.'
                ) % (template.name, self.integration_id.name))

            external_template.run_import_products(trigger_export_other=self.export_to_other)
