# Copyright 2026 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).


{
    "name": "eFarmer Hr Payroll",
    "version": "19.0.1.0.0",
    "category": "Other",
    "author": "VentorTech",
    "website": "https://ventor.tech",
    "license": "LGPL-3",
    "depends": [
        "hr_payroll",
        "hr_work_entry_enterprise",
    ],
    "data": [
        # Security
        "security/ir.model.access.csv",
        # Wizard Views
        "wizards/hr_payslip_import_wizard.xml",
    ],
    "installable": True,
    "application": True,
}
