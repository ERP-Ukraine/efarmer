from odoo import api, models


class ProductLabelLayout(models.TransientModel):
    _inherit = 'lot.label.layout'

    @api.depends('print_format', 'zld_label_id')
    def _compute_printer_id(self):
        """
        Overrides _compute_printer_id to add dependency on 'zld_label_id'.
        """
        return super()._compute_printer_id()

    def _prepare_report_data(self):
        """
        Overrides _prepare_report_data to add correct xml_id for ZPL Designer labels.
        """
        if self.print_format == 'zld_label':
            if self.zld_label_id:
                xml_id = self.zld_label_id.action_report_id.xml_id

                # This method should return xml_id and data. But we don't need data in this case
                return xml_id, None

        return super()._prepare_report_data()
