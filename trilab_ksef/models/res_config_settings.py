from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    x_ksef_settings_id = fields.Many2one(related='company_id.x_ksef_settings_id', readonly=False)

    x_ksef_enable_barcodes = fields.Boolean(related='company_id.x_ksef_enable_barcodes', readonly=False)
    x_ksef_enable_ignore_zero_amount_lines = fields.Boolean(
        related='company_id.x_ksef_enable_ignore_zero_amount_lines', readonly=False
    )
    x_ksef_purchase_journal_id = fields.Many2one(related='company_id.x_ksef_purchase_journal_id', readonly=False)
    x_ksef_purchase_invoice_sync_date = fields.Datetime(
        related='company_id.x_ksef_purchase_invoice_sync_date', readonly=False
    )

    x_ksef_plain_token = fields.Char(related='company_id.x_ksef_plain_token', readonly=False)
    x_ksef_plain_verification_link_certificate_datas = fields.Binary(
        related='company_id.x_ksef_plain_verification_link_certificate_datas', readonly=False
    )
    x_ksef_verification_link_certificate_name = fields.Char(
        related='company_id.x_ksef_verification_link_certificate_name', readonly=False
    )

    x_ksef_plain_verification_link_private_key_datas = fields.Binary(
        related='company_id.x_ksef_plain_verification_link_private_key_datas', readonly=False
    )
    x_ksef_verification_link_private_key_name = fields.Char(
        related='company_id.x_ksef_verification_link_private_key_name', readonly=False
    )

    x_ksef_plain_verification_link_private_key_password = fields.Char(
        related='company_id.x_ksef_plain_verification_link_private_key_password', readonly=False
    )

    default_x_ksef_invoice_date_applicability = fields.Selection(
        selection=[
            ('common', 'A common date of supply or completion of services applicable to the entire invoice.'),
            ('itemized', 'Different delivery or service completion dates for individual goods or services.'),
        ],
        default='common',
        default_model='account.move',
    )
