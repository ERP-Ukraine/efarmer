from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    default_used_warehouse_id = fields.Many2one(
        comodel_name='stock.warehouse',
        string='Default Used Warehouse',
        default_model='efarmer.helpdesk.repair',
    )
