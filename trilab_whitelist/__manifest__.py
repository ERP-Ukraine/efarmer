# noinspection PyStatementEffect
{
    'name': 'Trilab MF WhiteList PL',
    'author': 'Trilab',
    'website': 'https://trilab.pl',
    'version': '18.0.2.0.0',
    'category': 'Accounting',
    'summary': 'Validate partner bank account via Ministry of Finance whitelist for Poland',
    'description': """
    Module implements method to access and validate partner bank account (on the invoice)
    with the Polish Ministry of Finance whitelist API - according to new rules and regulations
    """,
    'depends': ['account'],
    'data': ['security/ir.model.access.csv', 'views/account_move.xml', 'wizard/partner_check_wl.xml'],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'OPL-1',
    'price': 20.0,
    'currency': 'EUR',
}
