{
    'name': 'Trilab Cash FIFO',
    'summary': 'Trilab Cash FIFO',
    'author': 'Trilab',
    'website': 'https://trilab.pl/',
    'category': 'Accounting/Accounting',
    'version': '18.0.2.0.0',
    'depends': ['account_accountant'],
    'data': [
        'data/mail_templates_chatter.xml',
        'views/account_bank_statement_line.xml',
        'views/account_journal.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'trilab_cash_fifo/static/src/components/bank_reconciliation/bank_rec_form.xml',
            'trilab_cash_fifo/static/src/components/bank_reconciliation/kanban.js',
        ],
    },
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'OPL-1',
    'price': 200.0,
    'currency': 'EUR',
}
