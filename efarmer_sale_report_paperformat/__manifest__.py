# -*- coding: utf-8 -*-
# pylint: disable=W0104
"""
eFarmer Sale Report Paperformat module manifest.
Provides a custom paper format for sale reports in Odoo.
"""

# Copyright 2025 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

{
    "name": "eFarmer Sale Report Paperformat",
    "version": "1.0",
    "category": "Others",
    "author": "VentorTech",
    "website": "https://ventor.tech",
    "license": "LGPL-3",
    "depends": [
        "sale",
    ],
    "description": "Adds a custom paper format for eFarmer sale reports.",
    "data": [
        "reports/efarmer_paperformat_sale_report.xml",
    ],
    "installable": True,
    "application": False,
}
