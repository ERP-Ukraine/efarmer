# -*- coding: utf-8 -*-
{
    "name": "eFarmer MRP Label Print",
    "version": "18.0.1.0.0",
    "category": "Manufacturing",
    "summary": "Bulk printing of stock labels for components and finished product of MO",
    "author": "VentorTech",
    "website": "https://ventor.tech/",
    "license": "LGPL-3",
    "depends": ["mrp", "efarmer_sale_workflow"],
    "data": [
        "security/ir.model.access.csv",
        "reports/mrp_label_print_report.xml",
        "wizard/mrp_label_print_wizard_views.xml",
        "data/ir_actions_server.xml",
    ],
    "auto_install": False,
    "installable": True,
    "application": False,
}
