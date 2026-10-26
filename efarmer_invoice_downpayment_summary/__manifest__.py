# Copyright 2026 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

{
    "name": "Efarmer Invoice Down Payment Summary",
    "summary": """
        Final invoice PDF with deducted down payments: summary of invoiced
        lines, applied down payments and the remaining amount (as in the
        Trilab FB final invoice).
    """,
    "version": "18.0.1.0.0",
    "category": "Accounting",
    "author": "VentorTech",
    "website": "https://ventor.tech",
    "license": "LGPL-3",
    "depends": [
        "sale",
        "efarmer_sale_workflow",
        # companies printing with the Trilab report (x_use_ti) are skipped
        "trilab_invoice",
    ],
    "data": [
        "reports/report_invoice.xml",
    ],
    "installable": True,
}
