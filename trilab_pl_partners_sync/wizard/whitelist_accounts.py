from odoo import _, api, fields, models


class WhitelistPartnerBank(models.TransientModel):
    _name = 'trilab.wl.partner.bank'
    _description = 'Trilab Whitelist Partner Bank Account Wizard'

    wl_wizard_id = fields.Many2one('trilab.wl.wizard')
    acc_number = fields.Char('Account Number')
    select = fields.Boolean('Select', default=False)


class WhitelistWizard(models.TransientModel):
    _name = 'trilab.wl.wizard'
    _description = 'Trilab Whitelist Wizard'

    banks_ids = fields.One2many('trilab.wl.partner.bank', 'wl_wizard_id')
    partner_id = fields.Many2one('res.partner')
    select_all = fields.Boolean('Select All', default=False)

    @api.onchange('select_all')
    def control_select_all(self):
        for bank_id in self.banks_ids:
            bank_id.select = self.select_all

    def save_selected_banks(self):
        self.ensure_one()

        selected_banks = self.banks_ids.filtered('select')

        if selected_banks:
            self.partner_id.write(
                {
                    'bank_ids': [
                        fields.Command.create({'acc_number': bank.acc_number, 'partner_id': self.partner_id})
                        for bank in selected_banks
                    ]
                }
            )

            self.partner_id.message_post(
                body=_(
                    'Bank accounts added from Whitelist of Ministry of Finance: %s',
                    ', '.join([bank.acc_number for bank in selected_banks]),
                )
            )
