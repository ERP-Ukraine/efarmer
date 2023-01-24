# Copyright 2023 VentorTech OU

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    youtrack_api_key = fields.Char(
        string='Token',
        config_parameter='youtrack_api_key',
    )

    youtrack_is_active = fields.Boolean(
        string='YouTrack API',
        config_parameter='youtrack_is_active',
    )
