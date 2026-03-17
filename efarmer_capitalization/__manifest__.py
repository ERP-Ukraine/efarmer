# Copyright 2026 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

{
    "name": "eFarmer Capitalization",
    "version": "19.0.1.0.0",
    "author": "VentorTech",
    "website": "https://ventor.tech/",
    "license": "LGPL-3",
    "category": "Services",
    "depends": [
        "account",
        "account_asset",
        "base",
        "efarmer_timesheet",
        "efarmer_youtrack",
        "product",
        "project",
        "hr",
        "hr_timesheet",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/project_capitalization_views.xml",
    ],
    "installable": True,
    "application": True,
}
