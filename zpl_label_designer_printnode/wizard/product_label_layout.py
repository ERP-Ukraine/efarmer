from odoo import api, models


DEFAULT_ZLD_LABEL_FIELD_BY_MODEL = {
    'product.template': 'print_pt_zld_label_id',
    'product.product': 'print_pp_zpl_label_id',
    'stock.picking': 'print_picking_zld_label_id',
    'mrp.production': 'print_mrp_zld_label_id',
    'stock.picking.batch': 'print_batch_zld_label_id',
}

ODOO_LABEL_FORMATS = {
    'dymo',
    '2x7xprice',
    '4x7xprice',
    '4x12',
    '4x12xprice',
    'zpl',
    'zplxprice',
}


class ProductLabelLayout(models.TransientModel):
    _name = 'product.label.layout'
    _inherit = ['product.label.layout', 'printnode.label.layout.mixin']

    @api.depends('print_format', 'zld_label_id')
    def _compute_printer_id(self):
        """
        Overrides _compute_printer_id to add dependency on 'zld_label_id'.
        """
        return super()._compute_printer_id()

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        wizard_label_format = self.env.company.print_wizard_label_format

        # Select the default print format for the wizard based on the company settings.
        # If the default format is one of Odoo's formats, use it.
        if wizard_label_format in ODOO_LABEL_FORMATS:
            res['print_format'] = wizard_label_format
            return res

        active_model = self.env.context.get('active_model')
        company_label = DEFAULT_ZLD_LABEL_FIELD_BY_MODEL.get(active_model)
        default_label = self.env.company[company_label] if company_label else False

        # Select ZPL Designer label if the default format for wizard is set to 'Label From ZPL Designer'
        # and a default label is set for the model
        if wizard_label_format == 'zld_label' and default_label:
            res['print_format'] = 'zld_label'
            res['zld_label_id'] = default_label.id

        return res
