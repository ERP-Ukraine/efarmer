from odoo import api, fields, models

KSEF_CLASSIFICATIONS = [
    ('1', 'Factor'),
    ('2', 'Recipient'),
    ('3', 'Original entity'),
    ('4', 'Additional buyer'),
    ('5', 'Invoice issuer'),
    ('6', 'Payer'),
    ('7', 'Local government unit - issuer'),
    ('8', 'Local government unit - recipient'),
    ('9', 'VAT group member - issuer'),
    ('10', 'VAT group member - recipient'),
    ('11', 'Employee'),
    ('-1', 'Other Role'),
]

KSEF_CLASSIFICATIONS_HELP = """* Faktor - w przypadku gdy na fakturze występują dane faktora
    * Odbiorca - w przypadku gdy na fakturze występują dane jednostek wewnętrznych, oddziałów, wyodrębnionych w ramach nabywcy, które same nie stanowią nabywcy w rozumieniu ustawy
    * Podmiot pierwotny - w przypadku gdy na fakturze występują dane podmiotu będącego w stosunku do podatnika podmiotem przejętym lub przekształconym, który dokonywał dostawy lub świadczył usługę. Z wyłączeniem przypadków, o których mowa w art. 106j ust.2 pkt 3 ustawy, gdy dane te wykazywane są w części Podmiot1K
    * Dodatkowy nabywca - w przypadku gdy na fakturze występują dane kolejnych (innych niż wymieniony w części Podmiot2) nabywców
    * Wystawca faktury - w przypadku gdy na fakturze występują dane podmiotu wystawiającego fakturę w imieniu podatnika. Nie dotyczy przypadku, gdy wystawcą faktury jest nabywca
    * Dokonujący płatności - w przypadku gdy na fakturze występują dane podmiotu regulującego zobowiązanie w miejsce nabywcy
    * Jednostka samorządu terytorialnego - wystawca
    * Jednostka samorządu terytorialnego - odbiorca
    * Członek grupy VAT - wystawca
    * Członek grupy VAT - odbiorca
    * Pracownik
    * Inny Rola - inny podmiot, wymagany opis roli podmiotu
    """


class KsefThirdParty(models.Model):
    _name = 'ksef.third_party'
    _description = 'KSeF Third Party'

    move_id = fields.Many2one('account.move')
    sale_order_id = fields.Many2one('sale.order')

    partner_id = fields.Many2one('res.partner', string='Partner', required=True)
    classification = fields.Selection(
        selection=KSEF_CLASSIFICATIONS,
        help=KSEF_CLASSIFICATIONS_HELP,
        compute='_compute_classification',
        required=True,
        store=True,
        readonly=False,
    )

    classification_other = fields.Char(
        string='Classification Other',
        compute='_compute_classification',
        store=True,
        readonly=False,
    )

    @api.depends('partner_id')
    def _compute_classification(self):
        for record_id in self:
            if record_id.partner_id.x_ksef_classification:
                record_id.classification = record_id.partner_id.x_ksef_classification
            if record_id.partner_id.x_ksef_classification_other:
                record_id.classification_other = record_id.partner_id.x_ksef_classification_other
