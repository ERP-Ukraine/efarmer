# -*- coding: UTF-8 -*-
# Copyright 2023 Solvve, Inc. <sales@solvve.com>

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    use_sale_hubspot_connector = fields.Boolean(
        string="Use Sale Hubspot Connector",
        default=False,
        config_parameter="hubspot_quotation_connector.use_sale_hubspot_connector",
    )
    sale_hubspot_config_id = fields.Many2one(
        comodel_name="hubspot.config",
        string="Sale HubSpot Config",
        config_parameter="hubspot_quotation_connector.sale_hubspot_config_id",
    )
