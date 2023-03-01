# -*- coding: UTF-8 -*-
# Copyright 2023 Solvve, Inc. <sales@solvve.com>

from hubspot import HubSpot
from odoo import api, fields, models


class HubSpotConfig(models.Model):
    _name = 'hubspot.config'
    _description = 'HubSpot Configuration'

    name = fields.Char(required=True)
    access_token = fields.Char(required=True)

    def _get_client(self) -> HubSpot:
        self.ensure_one()
        return HubSpot(access_token=self.access_token)
