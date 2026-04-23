import re

from stdnum.pl import nip as std_pl_nip

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .ksef_third_party import KSEF_CLASSIFICATIONS, KSEF_CLASSIFICATIONS_HELP

KSEF_INTERNAL_ID_PATTERN_RE = re.compile(r'^([1-9]((\d[1-9])|([1-9]\d))\d{7})-(\d{5})$')


class ResPartner(models.Model):
    _inherit = 'res.partner'

    x_ksef_purchase_journal_id = fields.Many2one(
        'account.journal',
        string='KSeF Purchase Journal',
        company_dependent=True,
        help='If set, this journal will be used for purchase invoices downloaded from KSeF '
        'for this partner, overriding the default journal configured on the company.',
    )

    x_ksef_classification = fields.Selection(
        string='KSeF Classification',
        selection=KSEF_CLASSIFICATIONS,
        help=KSEF_CLASSIFICATIONS_HELP,
    )
    x_ksef_classification_other = fields.Char(string='KSeF Classification Other')
    x_ksef_gln = fields.Char(string='KSeF GLN', size=13, copy=False, help='Global Location Number')
    x_ksef_eori = fields.Char(
        string='KSeF Nr EORI',
        copy=False,
        help='EU Economic Operator Identification and Registration Number',
    )
    x_ksef_internal_id = fields.Char(
        string='KSeF Internal ID',
        copy=False,
        help="Unique KSeF internal identifier (IDWew) composed of the taxpayer's NIP and an assigned unit number. "
        'Expected format: XXXXXXXXXX-XXXXX (e.g. 1234567891-12345).',
    )

    x_ksef_disable_shipping_third_party = fields.Boolean(
        string='KSeF Do not send Shipping Partner as Third Party',
        help='When enabled, shipping partner will not be automatically included as a shipping third party '
        '(Podmiot3, role: Recipient) in KSeF XML, even if set as the delivery address. '
        'Also applies to contacts belonging to this partner.',
    )

    @api.constrains('x_ksef_internal_id')
    def _x_ksef_internal_id(self):
        for partner_id in self:
            if not partner_id.x_ksef_internal_id:
                continue

            if not (match := KSEF_INTERNAL_ID_PATTERN_RE.match(partner_id.x_ksef_internal_id)):
                raise ValidationError(_('KSeF Internal ID has invalid format.'))

            try:
                if not std_pl_nip.is_valid(match.group(1)):
                    raise ValidationError(_('KSeF Internal ID contains an invalid NIP number.'))
            except std_pl_nip.ValidationError as error:
                raise ValidationError(str(error)) from error
