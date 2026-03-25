# noinspection PyStatementEffect
{
    'name': 'Trilab JPK Base',
    'summary': """
        Base module used by all Trilab JPK modules.
    """,
    'description': """
    Base module used by all Trilab JPK modules, provides basic data dictionaries and necessary extensions.
""",
    'author': 'Trilab',
    'website': 'https://trilab.pl',
    'category': 'Accounting',
    'version': '15.0.38.1.1',
    'depends': ['account'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/data.xml',
        'data/jpk_gtu.xml',
        'views/menu.xml',
        'views/jpk_document_type.xml',
        'views/jpk_gtu.xml',
        'views/res_company_views.xml',
        'views/account_tag.xml',
        'views/account_move.xml',
        'views/account_journal.xml',
        'views/product.xml',
        'views/res_partner_views.xml',
    ],
    'demo': [],
    'images': ['static/description/banner.png'],
    'installable': True,
    'auto_install': False,
    'application': True,
    'license': 'OPL-1',
    'post_init_hook': 'post_init_handler',
    'uninstall_hook': 'uninstall_handler',
}
