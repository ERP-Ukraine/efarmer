from odoo import fields, models


class AccountAnalyticPlan(models.Model):
    _inherit = 'account.analytic.plan'

    x_pl_jpk_kr_pd = fields.Boolean(
        'PL - JPK KR PD',
        help='Use analytic accounts from this plan as PD classification in JPK KR PD.',
        export_string_translation=False,
    )
