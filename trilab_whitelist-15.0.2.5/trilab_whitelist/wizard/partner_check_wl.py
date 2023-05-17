from odoo import models, fields, api


class CheckWhitelistDetail(models.TransientModel):
    _name = 'trilab.check.wl.detail'
    _description = 'Trilab Check Whitelist Detail Wizard'

    check_id = fields.Many2one('trilab.check.wl')
    invoice_id = fields.Many2one('account.move')

    name = fields.Char(related='invoice_id.name', string='Invoice Number')
    invoice_partner_display_name = fields.Char(related='invoice_id.invoice_partner_display_name', string='Partner')
    invoice_partner_bank_acc = fields.Char(
        related='invoice_id.partner_bank_id.sanitized_acc_number', string='Partner Bank Account'
    )

    is_error = fields.Boolean(compute='_compute_status')
    is_warning = fields.Boolean(compute='_compute_status')
    is_success = fields.Boolean(compute='_compute_status')
    error_type = fields.Selection(
        selection=[
            ('invalid_vat', 'Invalid VAT'),
            ('invalid_bank_acc', 'Invalid Bank Account'),
            ('positive', 'Positive Validation'),
            ('negative', 'Negative Validation'),
            ('api_error', 'API Error'),
        ],
        string='Validation Result',
    )
    error_message = fields.Char(string='Message')

    @api.depends('error_type')
    def _compute_status(self):
        for rec in self:
            rec.is_error = rec.is_success = rec.is_warning = False

            if rec.error_type:
                if rec.error_type in ('invalid_bank_acc', 'invalid_vat'):
                    rec.is_warning = True

                elif rec.error_type == 'positive':
                    rec.is_success = True

                else:
                    rec.is_error = True


class CheckWhitelist(models.TransientModel):
    _name = 'trilab.check.wl'
    _description = 'Trilab Check Whitelist Wizard'

    check_ids = fields.One2many('trilab.check.wl.detail', 'check_id')
