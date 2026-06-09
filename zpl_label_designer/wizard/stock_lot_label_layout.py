from collections import defaultdict
from odoo import exceptions, fields, models, _


class ProductLabelLayout(models.TransientModel):
    _inherit = 'lot.label.layout'

    print_format = fields.Selection(
        selection_add=[('zld_label', 'Label From ZPL Designer')],
        ondelete={'zld_label': 'set default'},
    )

    zld_label_id = fields.Many2one(
        string='Label from ZPL Designer',
        comodel_name='zld.label',
        domain='[("is_published", "=", True), ("model_id", "=", "stock.lot")]',
    )

    def process(self):
        self.ensure_one()

        if not self.print_format == 'zld_label':
            return super().process()

        if not self.zld_label_id:
            raise exceptions.UserError(_('Please select a ZPL Designer label'))

        xml_id = self.zld_label_id.action_report_id.xml_id

        # The rest of logic is the same as in the original method
        if self.label_quantity == 'lots':
            docids = self.move_line_ids.lot_id.ids
        else:
            uom_categ_unit = self.env.ref('uom.product_uom_categ_unit')
            quantity_by_lot = defaultdict(int)

            for move_line in self.move_line_ids:
                if not move_line.lot_id:
                    continue
                if move_line.product_uom_id.category_id == uom_categ_unit:
                    quantity_by_lot[move_line.lot_id.id] += int(move_line.quantity)
                else:
                    quantity_by_lot[move_line.lot_id.id] += 1

            docids = []
            for lot_id, qty in quantity_by_lot.items():
                docids.append([lot_id] * qty)

        report_action = self.env.ref(xml_id).report_action(docids, config=False)
        report_action.update({'close_on_report_download': True})

        return report_action
