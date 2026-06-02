from odoo import _, exceptions, fields, models


PRODUCT_LABEL_MODELS_MAPPING = {
    'product.template': 'product.template',
    'product.product': 'product.product',
    'stock.picking': 'product.product',
    'picking.label.type': 'product.product',
    'quality.check': 'product.product',
    'mrp.production': 'product.product',
    'stock.picking.batch': 'product.product',
}


class ProductLabelLayout(models.TransientModel):
    _inherit = 'product.label.layout'

    print_format = fields.Selection(
        selection_add=[('zld_label', 'Label From ZPL Designer')],
        ondelete={'zld_label': 'set default'}
    )

    zld_label_id = fields.Many2one(
        string='Label from ZPL Designer',
        comodel_name='zld.label',
        domain=lambda self: self._get_zld_label_domain(),
    )

    def _get_zld_label_domain(self):
        return [
            ('is_published', '=', True),
            ('model_id', '=', PRODUCT_LABEL_MODELS_MAPPING.get(self._context.get('active_model')))
        ]

    def _prepare_report_data(self):
        xml_id, data = super()._prepare_report_data()

        if self.print_format == 'zld_label':
            if self.zld_label_id:
                xml_id = self.zld_label_id.action_report_id.xml_id

                # Mark the label as Product Label, so we will manually add docids later (check
                # 'ir.actions.report' model for details)
                data['is_zld_product_label'] = True

            else:
                xml_id = ''

        return xml_id, data

    def process(self):
        self.ensure_one()

        if self.print_format == 'zld_label' and not self.zld_label_id:
            raise exceptions.UserError(_('Please select a ZPL Designer label'))

        return super().process()
