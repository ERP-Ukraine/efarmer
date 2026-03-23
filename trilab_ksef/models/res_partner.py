from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    x_ksef_purchase_journal_id = fields.Many2one(
        'account.journal',
        string='KSeF Purchase Journal',
        company_dependent=True,
        help='If set, this journal will be used for purchase invoices downloaded from KSeF '
        'for this partner, overriding the default journal configured on the company.',
    )
