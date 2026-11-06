# noinspection PyStatementEffect
{
    'name': 'Trilab JPK KR PD',
    'summary': 'Generate JPK KR PD',
    'description': """
        Generate report for JPK (Jednolity Plik Kontrolny) Księgi Rachunkowe Podatek Dochodowy,
        required for accounting reporting in Poland
    """,
    'author': 'Trilab',
    'website': 'https://trilab.pl',
    'category': 'Accounting',
    'version': '18.0.4.0.0',
    'depends': ['trilab_jpk_base'],
    'data': [
        'security/ir.model.access.csv',
        'views/analytic_plan_views.xml',
        'views/reports.xml',
        'report/jpk_kr_pd_report.xml',
        'wizard/jpk_kr_pd_report.xml',
    ],
    'images': ['static/description/banner.png'],
    'application': True,
    'license': 'OPL-1',
    'price': 240.0,
    'currency': 'EUR',
}
