from odoo import api, models, _
from odoo.exceptions import UserError


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    @api.model
    def _get_rendering_context(self, report, docids, data):
        res = super()._get_rendering_context(report, docids, data)
        doc_model = res.get("doc_model")
        if doc_model == "mrp.production":
            for object in self.env["mrp.production"].browse(res.get("doc_ids")):
                if not object.lot_producing_ids:
                    raise UserError(
                        _('The "Lot/Serial Number" field must be populated.')
                    )
        return res
