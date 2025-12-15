# noinspection PyStatementEffect
{
    'name': "Trilab PL Financial Reports",

    'summary': """
        Trilab PL Financial Reports: Balance and P&L
        """,

    'description': """
        Structure for the financial reports Balance and P&L according to polish account rules and in accordance
         to electronic reports for IRS.
    """,

    'author': "Trilab",
    'website': "https://trilab.pl",

    'category': 'Accounting',
    'version': '15.0.3.0.0',

    'depends': ['account_reports'],

    'data': [
        # Tags
        'data/trilab_accounting_tags.xml',
        'data/trilab_analytic_tags.xml',

        # Reports
        'data/trilab_balance_sheet_report.xml',
        'data/trilab_pl_RZiSPor_report.xml',
        'data/trilab_pl_RZiSKalk_report.xml',
        'data/trilab_pl_CIT_report.xml',
    ],
    'images': [
        'static/description/banner.png'
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
    'license': 'OPL-1'
}
