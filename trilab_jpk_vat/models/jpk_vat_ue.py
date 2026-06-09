import base64
from collections import defaultdict

from odoo import Command, api, fields, models
from odoo.addons.trilab_jpk_vat.reports.jpk_vat_ue import JpkVatEuReport


class VatEuGroup(models.Model):
    _name = 'jpk.vat.ue.group'
    _description = 'VAT EU Group'

    group = fields.Selection(
        [(k, v['name']) for k, v in JpkVatEuReport.GROUP_MAPPING.items()], string='JPK UE Group', required=True
    )
    country_code = fields.Char(string='Country Code', required=True)
    nip = fields.Char(string='NIP', required=True)
    amount = fields.Float(string='Amount')
    tt = fields.Char(string='Trilateral Transaction')
    vat_ue_id = fields.Many2one('jpk.vat.ue', string='Report', required=True, ondelete='cascade')

    @api.model
    def get_modified_lines(self, original_line_ids, correction_line_ids):
        values_ids_map = defaultdict(self.env['jpk.vat.ue.group'].browse)

        for line_id in original_line_ids | correction_line_ids:
            matching_key = (line_id.group, line_id.country_code, line_id.nip, line_id.amount, line_id.tt)
            values_ids_map[matching_key] += line_id

        modified_group_line_ids = self.env['jpk.vat.ue.group']

        # Keep only lines that are unique
        for line_ids in values_ids_map.values():
            if len(line_ids) == 1:
                modified_group_line_ids += line_ids

        return modified_group_line_ids


class VatEu(models.Model):
    _name = 'jpk.vat.ue'
    _inherit = 'jpk.document.mixin'
    _description = 'VAT UE'

    source_xml = fields.Binary()

    group_line_ids = fields.One2many('jpk.vat.ue.group', 'vat_ue_id', string='Group Lines')
    group1_line_ids = fields.One2many('jpk.vat.ue.group', compute='_compute_group_lines', string='Group1 Lines')
    group2_line_ids = fields.One2many('jpk.vat.ue.group', compute='_compute_group_lines', string='Group2 Lines')
    group3_line_ids = fields.One2many('jpk.vat.ue.group', compute='_compute_group_lines', string='Group3 Lines')

    original_vat_ue_id = fields.Many2one('jpk.vat.ue', string='Original VAT UE', readonly=True, copy=False)

    original_group1_line_ids = fields.One2many(
        'jpk.vat.ue.group',
        compute='_compute_group_lines',
        string='Original Group1 Lines',
    )
    original_group2_line_ids = fields.One2many(
        'jpk.vat.ue.group',
        compute='_compute_group_lines',
        string='Original Group2 Lines',
    )
    original_group3_line_ids = fields.One2many(
        'jpk.vat.ue.group',
        compute='_compute_group_lines',
        string='Original Group3 Lines',
    )

    is_jpk_transfer_installed = fields.Boolean(compute='_compute_is_jpk_transfer_installed', readonly=True)

    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    @api.depends('group_line_ids', 'original_vat_ue_id.group_line_ids')
    def _compute_group_lines(self):
        for report_id in self:
            for field in (
                'group1_line_ids',
                'group2_line_ids',
                'group3_line_ids',
                'original_group1_line_ids',
                'original_group2_line_ids',
                'original_group3_line_ids',
            ):
                report_id[field] = [Command.clear()]

            if not report_id.original_vat_ue_id:
                for line_id in report_id.group_line_ids:
                    report_id[f'{line_id.group}_line_ids'] |= line_id
                continue

            modified_group_line_ids = self.env['jpk.vat.ue.group'].get_modified_lines(
                original_line_ids=report_id.original_vat_ue_id.group_line_ids,
                correction_line_ids=report_id.group_line_ids,
            )

            for original_line_id in report_id.original_vat_ue_id.group_line_ids & modified_group_line_ids:
                report_id[f'original_{original_line_id.group}_line_ids'] |= original_line_id

            for line_id in report_id.group_line_ids & modified_group_line_ids:
                report_id[f'{line_id.group}_line_ids'] |= line_id

    # noinspection HttpUrlsUsage
    # noinspection PyUnusedLocal
    def get_xml(self, options=None):
        return base64.b64decode(self.source_xml)

    # noinspection PyUnusedLocal
    def _compute_is_jpk_transfer_installed(self):
        self.is_jpk_transfer_installed = self.env.company.x_is_jpk_transfer_installed()

    def action_generate_xml(self):
        return {
            'type': 'ir.actions.report',
            'report_name': 'trilab_jpk_vat.jpk_vat_eu_report',
            'report_type': 'jpk_xml',
            'report_file': 'trilab_jpk_vat.jpk_vat_eu_report',
            'name': 'VAT UE',
            'context': {'active_ids': self.ids},
        }

    def action_transfer_xml(self):
        document_type = 'trilab_jpk_base.vat_ue5_v2_0e_doc_type'

        # noinspection PyUnresolvedReferences
        transfer_id = self.env['jpk.transfer'].create_with_document(
            {
                'name': f'VAT UE {self.month}/{self.year}',
                'jpk_type': 'JPK',
                'file_name': f'vat_ue_{self.month}_{self.year}.xml',
                'reference_document': f'{self._name},{self.id}',
                'data': self.get_xml(),
                'document_type': document_type,
            }
        )

        # noinspection PyUnresolvedReferences
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'jpk.transfer',
            'res_id': transfer_id.id,
            'view_mode': 'form',
            # 'target': 'new'
        }

    # noinspection PyMethodMayBeStatic
    def action_cancel(self):
        return {'type': 'ir.actions.act_window_close'}

    def action_generate_pdf(self):
        return self.env.ref('trilab_jpk_vat.report_vat_ue_pdf').report_action(self)

    def get_print_report_name(self):
        return f'vat_ue_{self.month:02d}_{self.year}{self.cel_zlozenia > 1 and "_korekta" or ""}'

    def action_transfer_correction_xml(self):
        document_type = 'trilab_jpk_base.vat_uek5_v2_1e_doc_type'

        # noinspection PyUnresolvedReferences
        transfer_id = self.env['jpk.transfer'].create_with_document(
            {
                'name': f'VAT UEK {self.month}/{self.year}',
                'jpk_type': 'JPK',
                'file_name': f'vat_uek_{self.month}_{self.year}.xml',
                'reference_document': f'{self._name},{self.id}',
                'data': self.get_xml(),
                'document_type': document_type,
            }
        )

        # noinspection PyUnresolvedReferences
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'jpk.transfer',
            'views': [[False, 'form']],
            'res_id': transfer_id.id,
        }
