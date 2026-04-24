from odoo import _, api, fields, models

MPP_EDGE_AMOUNT = 15_000.00

X_PL_VAT_OUT_TYPES = [
    ('RO', 'dokument zbiorczy wewnętrzny zawierający sprzedaż z kas rejestrujących'),
    ('FP', 'faktura do paragonu, o której mowa w art. 109 ust. 3d ustawy'),
    ('WEW', 'dokument wewnętrzny'),
]

X_PL_VAT_IN_TYPES = [
    ('MK', 'metoda kasowa'),
    ('VAT_RR', 'faktury VAT RR, o której mowa w art. 116 ustawy'),
    ('WEW', 'dokument wewnętrzny'),
]


class AccountMove(models.Model):
    _inherit = 'account.move'
    _sql_constraints = [
        ('unique_journal_entry_number', 'unique (x_journal_entry_number)', 'Journal Entry Number must be unique.'),
    ]

    pl_vat_date = fields.Date(string='VAT Date', index=True, export_string_translation=False)

    x_pl_vat_typ_dokumentu = fields.Selection(
        string='Typ Dokumentu',
        selection=X_PL_VAT_OUT_TYPES,
        tracking=True,
        help='Oznaczenia dowodu sprzedaży',
        export_string_translation=False,
    )

    x_pl_vat_dokument_zakupu = fields.Selection(
        string='Dokument Zakupu',
        selection=X_PL_VAT_IN_TYPES,
        help='Oznaczenie dowodu zakupu',
        export_string_translation=False,
    )

    x_pl_vat_mpp = fields.Boolean(
        string='MPP',
        default=False,
        tracking=True,
        help='Transakcja objęta obowiązkiem stosowania mechanizmu podzielonej płatności. '
        'Oznaczenie MPP należy stosować do faktur o kwocie brutto wyższej niż 15 000,00 zł, '
        'które dokumentują dostawę towarów lub świadczenie usług wymienionych w załączniku nr 15 do ustawy.',
        export_string_translation=False,
    )

    # sprzedaż
    x_pl_vat_sw = fields.Boolean(
        string='SW',
        default=False,
        help='Dostawa w ramach sprzedaży wysyłkowej z terytorium kraju, o której mowa w art. 23 ustawy',
        export_string_translation=False,
    )
    x_pl_vat_ee = fields.Boolean(
        string='EE',
        default=False,
        help='Świadczenie usług telekomunikacyjnych, nadawczych i elektronicznych, o których mowa w art. 28k ustawy',
        export_string_translation=False,
    )
    x_pl_vat_tp = fields.Boolean(
        string='TP',
        default=False,
        help='Istniejące powiązania między nabywcą a dokonującym dostawy towarów lub '
        'usługodawcą, o których mowa w art. 32 ust. 2 pkt 1 ustawy.',
        export_string_translation=False,
    )
    x_pl_vat_tt_wnt = fields.Boolean(
        string='TT-WNT',
        default=False,
        help='Wewnątrzwspólnotowe nabycie towarów dokonane przez drugiego w kolejności '
        'podatnika VAT w ramach transakcji trójstronnej w procedurze uproszczonej, '
        'o której mowa w dziale XII rozdział 8 ustawy.',
        export_string_translation=False,
    )
    x_pl_vat_tt_d = fields.Boolean(
        string='TT-D',
        default=False,
        help='Dostawa towarów poza terytorium kraju dokonana przez drugiego w kolejności '
        'podatnika VAT w ramach transakcji trójstronnej w procedurze uproszczonej, '
        'o której mowa w dziale XII rozdział 8 ustawy.',
        export_string_translation=False,
    )
    x_pl_vat_mr_t = fields.Boolean(
        string='MR-T',
        default=False,
        help='Świadczenie usług turystyki opodatkowane na zasadach marży zgodnie z art. 119 ustawy.',
        export_string_translation=False,
    )
    x_pl_vat_mr_uz = fields.Boolean(
        string='MR-UZ',
        default=False,
        help='Dostawa towarów używanych, dzieł sztuki, przedmiotów kolekcjonerskich '
        'i antyków, opodatkowana na zasadach marży zgodnie z art. 120 ustawy.',
        export_string_translation=False,
    )
    x_pl_vat_i42 = fields.Boolean(
        string='I42',
        default=False,
        help='Wewnątrzwspólnotowa dostawa towarów następująca po imporcie tych towarów '
        'w ramach procedury celnej 42 (import).',
        export_string_translation=False,
    )
    x_pl_vat_i63 = fields.Boolean(
        string='I63',
        default=False,
        help='Wewnątrzwspólnotowa dostawa towarów następująca po imporcie tych towarów '
        'w ramach procedury celnej 63 (import).',
        export_string_translation=False,
    )
    x_pl_vat_b_spv = fields.Boolean(
        string='B-SPV',
        default=False,
        help='Transfer bonu jednego przeznaczenia dokonany przez podatnika działającego '
        'we własnym imieniu, opodatkowany zgodnie z art. 8a ust. 1 ustawy.',
        export_string_translation=False,
    )
    x_pl_vat_b_spv_dostawa = fields.Boolean(
        string='B-SPV Dostawa',
        default=False,
        help='Dostawa towarów oraz świadczenie usług, których dotyczy bon jednego '
        'przeznaczenia na rzecz podatnika, który wyemitował bon zgodnie '
        'z art. 8a ust. 4 ustawy.',
        export_string_translation=False,
    )
    x_pl_vat_b_mpv_prowizja = fields.Boolean(
        string='B-MPV Prowizja',
        default=False,
        help='Świadczenie usług pośrednictwa oraz innych usług dotyczących '
        'transferu bonu różnego przeznaczenia, opodatkowane zgodnie '
        'z art. 8b ust. 2 ustawy.',
        export_string_translation=False,
    )
    x_pl_vat_korekta_podstawy_opodt = fields.Boolean(
        string='Korekta Podstawy Opodatkowania',
        default=False,
        tracking=True,
        help='Korekta podstawy opodatkowania oraz podatku należnego, o której mowa w art. 89a ust. 1 i 4 ustawy',
        export_string_translation=False,
    )
    x_pl_vat_reverse_charge = fields.Boolean(string='Reverse charge', default=False, tracking=True)

    x_pl_vat_wsto_ee = fields.Boolean(string='WSTO_EE', export_string_translation=False)
    x_pl_vat_ied = fields.Boolean(string='IED', export_string_translation=False)
    x_pl_change_jpk_proof = fields.Char(string='Change JPK Proof Document')

    # zakup
    x_pl_vat_imp = fields.Boolean(
        string='IMP',
        default=False,
        help='Oznaczenie dotyczące podatku naliczonego z tytułu importu towarów, '
        'w tym importu towarów rozliczanego zgodnie z art. 33a ustawy.',
        export_string_translation=False,
    )

    x_pl_ksef_invoice_number = fields.Char(string='KSeF Invoice Number', readonly=True, copy=False, index=True)
    x_pl_ksef_invoice_proof = fields.Selection(
        [
            ('OFF', 'OFF'),
            ('BFK', 'BFK'),
            ('DI', 'DI'),
        ],
        string='KSeF Invoice Proof',
        help='Dane z faktur lub oznaczenia dotyczące występowania faktur w Krajowym Systemie e-Faktur\n'
        'OFF - Faktura, o której mowa w art. 106nf ust. 1 ustawy, która na dzień złożenia ewidencji nie posiada '
        'numeru identyfikującego tę fakturę w Krajowym Systemie e-Faktur\n'
        'BFK - Faktura elektroniczna lub faktura w postaci papierowej\n'
        'DI - Dowód inny niż faktura',
    )

    x_journal_entry_number = fields.Char(
        'Journal Entry Number', readonly=True, copy=False, help='Sequential journal entry number.'
    )

    def _x_assign_mpp(self):
        base_pl_id = self.env.ref('base.pl')
        pln_currency_id = self.env.ref('base.PLN')

        # noinspection PyUnboundLocalVariable
        for move_id in self.filtered(
            lambda m_id: m_id.move_type == 'out_invoice'
            and not m_id.x_pl_vat_mpp
            and m_id.partner_id.is_company
            and (partner_vat := m_id.partner_id.vat)
            and (m_id.partner_id.country_id == base_pl_id or partner_vat[:2] == 'PL')
            and any(m_id.invoice_line_ids.product_id.product_tmpl_id.mapped('x_pl_vat_mpp'))
            and m_id.currency_id.compare_amounts(
                m_id.currency_id._convert(
                    m_id.amount_total,
                    pln_currency_id,
                    m_id.company_id,
                    m_id.invoice_date or m_id.date or fields.Date.context_today(m_id),
                ),
                MPP_EDGE_AMOUNT,
            )
            >= 0
        ):
            move_id.x_pl_vat_mpp = True
            move_id.message_post(body=_('The invoice was marked with the split payment mechanism'))

    def action_post(self):
        response = super().action_post()

        self._x_assign_mpp()

        for move_id in self.filtered(lambda m_id: m_id.is_invoice(include_receipts=True) and not m_id.pl_vat_date):
            if (
                move_id.invoice_date
                and move_id.is_sale_document(include_receipts=True)
                and hasattr(move_id, 'x_invoice_sale_date')
            ):
                date = move_id.x_invoice_sale_date
            else:
                date = move_id.date

            move_id.pl_vat_date = date

        return response

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        if self.is_sale_document() and self.x_pl_vat_typ_dokumentu != 'WEW':
            self.x_pl_vat_tp = self.partner_id.x_pl_vat_tp

    @api.onchange('journal_id')
    def _x_onchange_journal_id(self):
        if self.is_sale_document():
            self.x_pl_vat_typ_dokumentu = self.journal_id.x_pl_vat_typ_dokumentu

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if (
                'x_pl_vat_tp' not in vals
                and vals.get('move_type', self._context.get('default_move_type')) in self.get_sale_types()
                and vals.get('x_pl_vat_typ_dokumentu') != 'WEW'
                and (partner_id := self.env['res.partner'].browse(vals.get('partner_id')))
            ):
                vals['x_pl_vat_tp'] = partner_id.x_pl_vat_tp

        return super().create(vals_list)

    def copy_data(self, default=None):
        data_list = super().copy_data(default)

        # Copy pl_vat_date on refunds only.
        for data in data_list:
            if data.get('reversed_entry_id') not in self.ids and 'pl_vat_date' in data:
                del data['pl_vat_date']

        return data_list
