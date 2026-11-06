from odoo import fields, models

from .account_move import X_PL_VAT_IN_TYPES, X_PL_VAT_OUT_TYPES


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    x_pl_vat_typ_dokumentu = fields.Selection(
        X_PL_VAT_OUT_TYPES,
        'Typ Dokumentu',
        help='Oznaczenia dowodu sprzedaży',
        export_string_translation=False,
    )

    x_pl_vat_dokument_zakupu = fields.Selection(
        X_PL_VAT_IN_TYPES,
        'Dokument Zakupu',
        help='Oznaczenie dowodu zakupu',
        export_string_translation=False,
    )
