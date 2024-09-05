import base64
from datetime import datetime, timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class VatUECorrection(models.TransientModel):
    _name = 'jpk.vat.vat.ue.correction'
    _description = 'VAT UE Correction wizard'

    reference_transfer = fields.Reference(selection='_reference_models', string='JPK Transfer')
    original_vat_ue_id = fields.Many2one('jpk.vat.ue', string='Original VAT UE', readonly=True)

    year = fields.Integer(related='original_vat_ue_id.year')
    month = fields.Integer(related='original_vat_ue_id.month')
    version = fields.Char(related='original_vat_ue_id.version')

    correction_vat_ue_id = fields.Many2one('jpk.vat.ue', string='Correction VAT UE', readonly=True)

    original_group1_line_ids = fields.One2many(
        related='original_vat_ue_id.group1_line_ids', string='Original Group1 Lines'
    )
    original_group2_line_ids = fields.One2many(
        related='original_vat_ue_id.group2_line_ids', string='Original Group2 Lines'
    )
    original_group3_line_ids = fields.One2many(
        related='original_vat_ue_id.group3_line_ids', string='Original Group3 Lines'
    )

    correction_group1_line_ids = fields.One2many(
        related='correction_vat_ue_id.group1_line_ids', string='Correction Group1 Lines'
    )
    correction_group2_line_ids = fields.One2many(
        related='correction_vat_ue_id.group2_line_ids', string='Correction Group2 Lines'
    )
    correction_group3_line_ids = fields.One2many(
        related='correction_vat_ue_id.group3_line_ids', string='Correction Group3 Lines'
    )

    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)

        if not self.env.company.x_is_jpk_transfer_installed():
            raise UserError(_('This action is only available with JPK Transfer module installed!'))

        return defaults

    @api.model
    def _reference_models(self):
        if self.env.company.x_is_jpk_transfer_installed():
            return [('jpk.transfer', 'JPK Transfer')]
        return []

    @api.model
    def _validate_reference_transfer(self, reference_transfer):
        return (
            getattr(reference_transfer, '_name') == 'jpk.transfer'
            and getattr(reference_transfer.reference_document, '_name') == 'jpk.vat.ue'
            and reference_transfer.state == 'confirmed'
        )

    def _create_correction_vat_ue(self):
        options = {
            'date': {
                'date_from': datetime(self.year, self.month, 1),
                'date_to': datetime(self.year, self.month, 1) + relativedelta(months=1) - timedelta(days=1),
            },
            'all_entries': False,  # only posted entries
            'original_vat_ue_id': self.original_vat_ue_id.id,
        }

        report_date = fields.Date.to_date(options['date']['date_from'])

        xml, group_vals_list = self.env['account.report.vat_ue'].get_xml_extended_vat_uek(options)

        return self.env['jpk.vat.ue'].create(
            {
                'version': '2-1E',
                'year': report_date.year,
                'month': report_date.month,
                'cel_zlozenia': 2,
                'source_xml': base64.b64encode(xml),
                'group_line_ids': [
                    fields.Command.create(
                        {
                            'country_code': val.get('country_code'),
                            'nip': val.get('vat'),
                            'amount': val.get('amount'),
                            'tt': val.get('tt'),
                            'group': group.lower(),
                        }
                    )
                    for group, vals in group_vals_list.items()
                    for val in vals
                ],
            }
        )

    @api.onchange('reference_transfer')
    def _onchange_reference_transfer(self):
        for wizard in self.filtered('reference_transfer'):
            if not wizard._validate_reference_transfer(wizard.reference_transfer):
                wizard.reference_transfer = None
                return {
                    'warning': {
                        'title': _("Warning"),
                        'message': _("A 'Transfer' must be 'JPK VAT UE' and 'Confirmed'!"),
                    }
                }

            wizard.original_vat_ue_id = wizard.reference_transfer.reference_document
            wizard.correction_vat_ue_id = wizard._create_correction_vat_ue()

    def action_generate_xml(self):
        return self.correction_vat_ue_id.action_generate_xml()

    def action_transfer_xml(self):
        return self.correction_vat_ue_id.action_transfer_correction_xml()

    def action_generate_pdf(self):
        return self.correction_vat_ue_id.action_generate_pdf()
