from odoo import fields, models

from .account_move import X_PL_VAT_IN_TYPES, X_PL_VAT_OUT_TYPES


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    x_pl_vat_typ_dokumentu = fields.Selection(
        string='Typ Dokumentu', selection=X_PL_VAT_OUT_TYPES, help='Oznaczenia dowodu sprzedaży'
    )

    x_pl_vat_dokument_zakupu = fields.Selection(
        string='Dokument Zakupu', selection=X_PL_VAT_IN_TYPES, help='Oznaczenie dowodu zakupu'
    )
