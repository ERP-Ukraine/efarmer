# noinspection PyStatementEffect
{
    'name': 'Trilab JPK VAT',
    'summary': """
        Generate JPK VAT XML
        """,
    'description': """
        Report and generate XML for JPK (Jednolity Plik Kontrolny) required for accounting reporting in Poland
    """,
    'author': 'Trilab',
    'website': 'https://trilab.pl',
    'category': 'Accounting',
    'version': '18.0.4.2.1',
    'depends': ['trilab_jpk_base', 'trilab_invoice'],
    'data': [
        'security/ir.model.access.csv',
        'data/trilab_vat_reports.xml',
        'views/account.xml',
        'views/jpk_vat_7m.xml',
        'views/jpk_vat_ue.xml',
        'reports/invoice_report.xml',
        'reports/jpk_vat7m.xml',
        'reports/jpk_vat7m_v3.xml',
        'reports/jpk_vat7m_pdf.xml',
        'reports/jpk_vat_ue.xml',
        'wizard/jpk_vat_7m.xml',
        'wizard/vat_ue_correction.xml',
    ],
    'images': ['static/description/banner.png'],
    'assets': {
        'web.report_assets_common': ['trilab_jpk_vat/static/src/scss/report.scss'],
        'web.assets_backend': ['trilab_jpk_vat/static/src/scss/backend.scss'],
    },
    'installable': True,
    'auto_install': False,
    'application': True,
    'license': 'OPL-1',
    'price': 240.0,
    'currency': 'EUR',
}
