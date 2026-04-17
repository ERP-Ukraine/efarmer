# noinspection PyStatementEffect
{
    'name': 'Trilab MF WhiteList PL',
    'author': 'Trilab',
    'website': "https://trilab.pl",
    'version': '2.5',
    'category': 'Accounting',
    'summary': 'Validate partner bank account via Ministry of Finance whitelist for Poland',
    'description': '''
    Module implements method to access and validate partner bank account (on the invoice)
    with the Polish Ministry of Finance whitelist API - according to new rules and regulations
    ''',
    'depends': [
        'base',
    ],
    'data': [
    ],
    'images': [
        'static/description/banner.png',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'OPL-1',
    'price': 20.0,
    'currency': 'EUR'
}
