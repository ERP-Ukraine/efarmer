import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError

# street name, then a house number anchored at the end of the string: "5", "5A", "1/3", "1-3", optionally followed
# by a unit ("m. 4", "lok. 5", "apt 2"). Digits inside the name ("ul. 3 Maja 12") stay in the name.
X_STREET_NUMBER_RE = re.compile(
    r'^(.+?)\s+(\d+[a-zA-Z]?(?:\s*[/-]\s*\d+[a-zA-Z]?)*(?:[\s,]*(?:lokal|lok|apt|m)\.?\s*\d+[a-zA-Z]?)?)$',
    flags=re.IGNORECASE,
)


class Company(models.Model):
    _inherit = 'res.company'

    pl_tax_office_id = fields.Many2one('jpk.taxoffice', 'PL Tax Office')
    pl_county = fields.Char('County')
    pl_community = fields.Char('Community')
    pl_post = fields.Char('Post')

    x_street_short = fields.Char('Street (without house number)', compute='_x_split_street_no')
    x_street_short_number = fields.Char('House Number (short)', compute='_x_split_street_no')
    x_jpk_email = fields.Char(
        'JPK E-mail', help="If set, this E-mail will be used for JPK VAT report instead of the company's one."
    )

    @api.depends('street', 'street2')
    def _x_split_street_no(self):
        for company_id in self.sudo():
            full_street = ' '.join(filter(None, (company_id.street, company_id.street2))).strip()
            match = X_STREET_NUMBER_RE.match(full_street)
            company_id.x_street_short = match.group(1) if match else full_street
            company_id.x_street_short_number = match.group(2) if match else None

    def x_is_jpk_transfer_installed(self):
        return bool(
            self.env['ir.module.module']
            .sudo()
            .search_count([('name', '=', 'trilab_jpk_transfer'), ('state', '=', 'installed')])
        )

    def x_get_jpk_email(self):
        self.ensure_one()
        email = self.x_jpk_email or self.email
        if not email:
            raise UserError(_('Please set company email'))
        return email
