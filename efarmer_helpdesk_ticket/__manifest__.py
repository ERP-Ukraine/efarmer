# -*- coding: utf-8 -*-

# Copyright 2026 VentorTech OU
{
    "name": "Helpdesk Ticket, eFarmer",
    "version": "19.0.1.0.0",
    "category": "Other",
    "author": "VentorTech",
    "website": "https://ventor.tech",
    "license": "LGPL-3",
    "demo": [],
    "depends": [
        "base",
        "stock",
        "helpdesk",
        "helpdesk_stock",
        "efarmer_helpdesk",
        "efarmer_sale_workflow",
    ],
    "data": [
        "security/ir.model.access.csv",
        "wizards/short_ticket_form_wizard.xml",
        "views/helpdesk_ticket_views.xml",
        "views/helpdesk_team_views.xml",
    ],
    "auto_install": False,
    "installable": True,
    "application": False,
}
