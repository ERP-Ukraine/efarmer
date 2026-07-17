# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from odoo import api, models, fields
from odoo.tools.misc import groupby


_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    vat = fields.Char(
        compute='_compute_vat_efarmer',
        inverse='_inverse_vat_efarmer',
        store=True,
    )

    def _compute_vat_efarmer(self):
        pass

    def _inverse_vat_efarmer(self):
        for partner in self:
            if partner.vat and not partner.is_company and not partner.parent_id:
                partner.is_company = True

    @api.model
    def _run_vat_test(self, vat_number, default_country, partner_is_company=True):
        if default_country and default_country.code == 'PL':
            _logger.info(f'VIES check was skipped for polish company {self.name} with VAT {vat_number}')
            return True
        return super()._run_vat_test(vat_number, default_country, partner_is_company)

    @api.model
    def _get_fiscal_positions(self):
        self.env.cr.execute(f"""
SELECT
    afpt2.country_code,
    ARRAY_AGG(afp.id ORDER BY afpt2.line_count DESC, afpt2.line_count / afpt2.total_count DESC) as position_ids,
    ARRAY_AGG(afpt2.line_count ORDER BY afpt2.line_count DESC, afpt2.line_count / afpt2.total_count DESC) as line_count
FROM (
    SELECT
        afpt.position_id,
        coalesce(afpt.country_id, coalesce(afp2.country_id,0)) AS country_code,
        COUNT(*) AS line_count,
        SUM(COUNT(*)) OVER (PARTITION BY afpt.position_id) AS total_count
    FROM account_fiscal_position_tax afpt
    JOIN account_fiscal_position afp2
        on afpt.position_id  = afp2.id
    GROUP BY afpt.position_id, coalesce(afpt.country_id, coalesce(afp2.country_id,0))
) afpt2
JOIN account_fiscal_position afp
    on afpt2.position_id  = afp.id
where afp.active AND afp.company_id = {self.env.company.id}
GROUP BY afpt2.country_code;
        """)

        return {r[0]: list(zip(r[1], r[2])) for r in self.env.cr.fetchall()}

    def _update_fiscal_positions(self):
        company_ids = self.env['res.company'].sudo().search([])
        fiscal_positions = {}
        for (company_id, country_id), partner_ids in groupby(
            self,
            key=lambda r: (r.company_id, r.country_id),
        ):
            for company in (company_id if company_id else company_ids):
                if not company.enable_fisc_pos_auto_calc:
                    continue

                if company.id not in fiscal_positions:
                    fiscal_positions[company.id] = self.sudo().with_company(company)._get_fiscal_positions()

                position = fiscal_positions[company.id]

                if country_id and country_id.id in position:
                    position_id = position[country_id.id][0][0]
                elif country_id and country_id.id not in position and 0 in position:
                    position_id = position[0][0][0]
                elif not country_id and 0 in position:
                    position_id = position[0][0][0]
                else:
                    continue
                for partner_id in partner_ids:
                    partner_id.with_company(company).sudo().write({
                        'property_account_position_id': position_id if position_id else False,
                    })
                    partner_id.sudo().with_company(company)._commercial_sync_to_children()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        base_contacts = self.env['res.partner']
        if len(vals_list) == len(records):
            for record, vals in zip(records, vals_list):
                if (
                    record == record.commercial_partner_id
                    and not vals.get("property_account_position_id", False)
                ):
                    base_contacts += record

        if base_contacts:
            base_contacts._update_fiscal_positions()

        return records

    def write(self, vals):
        res = super().write(vals)

        if 'country_id' in vals and not vals.get('property_account_position_id', False):
            self.filtered(lambda r: r.commercial_partner_id)._update_fiscal_positions()

        return res
