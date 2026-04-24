# noinspection PyStatementEffect
{
    'name': 'Trilab Partners Sync for Poland (GUS/WHITELIST/VIES/KRD)',
    'summary': 'Sync Partner data from GUS (Główny Urząd Statystyczny) '
    'and validate it with GUS/MF WHITELIST/EU VIES/KRD',
    'author': 'Trilab',
    'website': 'https://trilab.pl',
    'category': 'Accounting',
    'version': '18.0.3.1.0',
    'depends': ['account', 'contacts', 'partner_autocomplete'],
    'external_dependencies': {'python': ['zeep', 'python-stdnum']},
    'data': [
        'security/groups.xml',
        'security/ir.model.access.csv',
        'data/cron.xml',
        'views/account_move.xml',
        'views/res_config_settings.xml',
        'views/res_partner.xml',
        'views/krd.xml',
        'wizard/partner_check.xml',
        'wizard/whitelist_accounts.xml',
    ],
    'images': ['static/description/banner.png'],
    'assets': {
        'web.assets_backend': [
            'trilab_pl_partners_sync/static/src/js/*',
            'trilab_pl_partners_sync/static/src/xml/*',
            'trilab_pl_partners_sync/static/src/scss/*',
        ]
    },
    'installable': True,
    'auto_install': False,
    'application': True,
    'license': 'OPL-1',
    'price': 10.0,
    'currency': 'EUR',
}
