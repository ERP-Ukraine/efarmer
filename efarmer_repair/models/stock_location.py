# Copyright 2025 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import models, fields


class Location(models.Model):
    _inherit = 'stock.location'

    is_repair_location_dest_id = fields.Boolean(
        string='Is a Repair Dest.Loc?',
        help='Check this box to allow using this location as the default destination location for all repair orders.'
    )
