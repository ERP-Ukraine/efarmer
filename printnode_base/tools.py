# Copyright 2021 VentorTech OU
# See LICENSE file for full copyright and licensing details.

from odoo import fields


def convert_iso_to_date(value):
    """
    Convert ISO date/datetime string to Odoo Date value.
    """
    if not value:
        return False

    return fields.Date.to_date(value)
