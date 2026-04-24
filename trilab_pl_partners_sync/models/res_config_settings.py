from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    x_pl_enable_gus = fields.Boolean(related='company_id.x_pl_enable_gus', readonly=False)
    x_pl_enable_krd = fields.Boolean(related='company_id.x_pl_enable_krd', readonly=False)

    x_pl_gus_api_key = fields.Char(string='GUS API Key', config_parameter='trilab_gusregon.x_pl_gus_api_key')

    x_pl_krd_env = fields.Selection(string='KRD env', related='company_id.x_pl_krd_env', readonly=False)
    x_pl_krd_login = fields.Char(string='KRD Login', related='company_id.x_pl_krd_login', readonly=False)
    x_pl_krd_pass = fields.Char(string='KRD Password', related='company_id.x_pl_krd_pass', readonly=False)

    x_pl_validate_vat = fields.Boolean(related='company_id.x_pl_validate_vat', readonly=False)
