import base64

from lxml import etree

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_repr

P_37_SUM_FIELDS = (
    'p_10',
    'p_11',
    'p_13',
    'p_15',
    'p_17',
    'p_19',
    'p_21',
    'p_22',
    'p_23',
    'p_25',
    'p_27',
    'p_29',
    'p_31',
)

P_38_PLUS_SUM_FIELDS = ('p_16', 'p_18', 'p_20', 'p_24', 'p_26', 'p_28', 'p_30', 'p_32', 'p_33', 'p_34')
P_38_MINUS_SUM_FIELDS = ('p_35', 'p_36')
P_38_SUM_FIELDS = P_38_PLUS_SUM_FIELDS + P_38_MINUS_SUM_FIELDS

P_48_SUM_FIELDS = ('p_39', 'p_41', 'p_43', 'p_44', 'p_45', 'p_46', 'p_47')

COMPUTED_FIELDS = ('p_37', 'p_38', 'p_48', 'p_51', 'p_53', 'p_62')


class JPKV7M(models.Model):
    _name = 'jpk.vat.7m'
    _description = 'JPK V7M/V7K'

    version = fields.Char(string='JPK Version')

    year = fields.Integer(string='Year')
    month = fields.Integer(string='Month')

    cel_zlozenia = fields.Integer(string='Cel złożenia')

    czesc_deklaracyjna = fields.Boolean(string='Część deklaracyjna', default=True)
    czesc_ewidencyjna = fields.Boolean(string='Część ewidencyjna', default=True)

    p_10 = fields.Integer(
        string='P_10',
        default=0,
        help='Zbiorcza wysokość podstawy opodatkowania z tytułu dostawy towarów oraz świadczenia usług na terytorium '
        'kraju, zwolnionych od podatku – wykazana w K_10',
    )
    p_11 = fields.Integer(
        string='P_11',
        default=0,
        help='Zbiorcza wysokość podstawy opodatkowania z tytułu dostawy towarów oraz świadczenia usług poza '
        'terytorium kraju – wykazana w K_11',
    )
    p_12 = fields.Integer(
        string='P_12',
        default=0,
        help='Zbiorcza wysokość podstawy opodatkowania z tytułu świadczenia usług, o których mowa w art. 100 ust. 1 '
        'pkt 4 ustawy – wykazana w K_12',
    )
    p_13 = fields.Integer(
        string='P_13',
        default=0,
        help='Zbiorcza wysokość podstawy opodatkowania z tytułu dostawy towarów oraz świadczenia usług na terytorium '
        'kraju, opodatkowanych stawką 0% – wykazana w K_13',
    )
    p_14 = fields.Integer(
        string='P_14',
        default=0,
        help='Zbiorcza wysokość podstawy opodatkowania z tytułu dostawy towarów, o której mowa w art. 129 ustawy '
        '– wykazana w K_14',
    )
    p_15 = fields.Integer(
        string='P_15',
        default=0,
        help='Zbiorcza wysokość podstawy opodatkowania z tytułu dostawy towarów oraz świadczenia usług na terytorium '
        'kraju, opodatkowanych stawką 5%, oraz korekty dokonanej zgodnie z art. 89a ust. 1 i 4 ustawy – wykazana w '
        'K_15',
    )
    p_16 = fields.Integer(
        string='P_16',
        default=0,
        help='Zbiorcza wysokość podatku należnego z tytułu dostawy towarów oraz świadczenia usług na terytorium kraju, '
        'opodatkowanych stawką 5%, oraz korekty dokonanej zgodnie z art. 89a ust. 1 i 4 ustawy – wykazana w K_16',
    )
    p_17 = fields.Integer(
        string='P_17',
        default=0,
        help='Zbiorcza wysokość podstawy opodatkowania z tytułu dostawy towarów oraz świadczenia usług na terytorium '
        'kraju, opodatkowanych stawką 7% albo 8%, oraz korekty dokonanej zgodnie z art. 89a ust. 1 i 4 ustawy '
        '– wykazana w K_17',
    )
    p_18 = fields.Integer(
        string='P_18',
        default=0,
        help='Zbiorcza wysokość podatku należnego z tytułu dostawy towarów oraz świadczenia usług na terytorium '
        'kraju, opodatkowanych stawką 7% albo 8%, oraz korekty dokonanej zgodnie z art. 89a ust. 1 i 4 ustawy '
        '– wykazana w K_18',
    )
    p_19 = fields.Integer(
        string='P_19',
        default=0,
        help='Zbiorcza wysokość podstawy opodatkowania z tytułu dostawy towarów oraz świadczenia usług na terytorium '
        'kraju, opodatkowanych stawką 22% albo 23%, oraz korekty dokonanej zgodnie z art. 89a ust. 1 i 4 ustawy '
        '– wykazana w K_19',
    )
    p_20 = fields.Integer(
        string='P_20',
        default=0,
        help='Zbiorcza wysokość podatku należnego z tytułu dostawy '
        'towarów oraz świadczenia usług na terytorium kraju, '
        'opodatkowanych stawką 22% albo 23%, oraz korekty '
        'dokonanej zgodnie z art. 89a ust. 1 i 4 ustawy '
        '– wykazana w K_20',
    )
    p_21 = fields.Integer(
        string='P_21',
        default=0,
        help='Zbiorcza wysokość podstawy opodatkowania z tytułu '
        'wewnątrzwspólnotowej dostawy towarów – wykazana w K_21',
    )
    p_22 = fields.Integer(
        string='P_22',
        default=0,
        help='Zbiorcza wysokość podstawy opodatkowania z tytułu ' 'eksportu towarów – wykazana w K_22',
    )
    p_23 = fields.Integer(
        string='P_23',
        default=0,
        help='Zbiorcza wysokość podstawy opodatkowania z tytułu '
        'wewnątrzwspólnotowego nabycia towarów – wykazana w K_23',
    )
    p_24 = fields.Integer(
        string='P_24',
        default=0,
        help='Zbiorcza wysokość podatku należnego z tytułu ' 'wewnątrzwspólnotowego nabycia towarów – wykazana w K_24',
    )
    p_25 = fields.Integer(
        string='P_25',
        default=0,
        help='Zbiorcza wysokość podstawy opodatkowania z tytułu '
        'importu towarów rozliczanego zgodnie z art. 33a ustawy '
        '– wykazana w K_25',
    )
    p_26 = fields.Integer(
        string='P_26',
        default=0,
        help='Zbiorcza wysokość podatku należnego z tytułu importu '
        'towarów rozliczanego zgodnie z art. 33a ustawy '
        '– wykazana w K_26',
    )
    p_27 = fields.Integer(
        string='P_27',
        default=0,
        help='Zbiorcza wysokość podstawy opodatkowania z tytułu '
        'importu usług, zwyłączeniem usług nabywanych od '
        'podatników podatku od wartości dodanej, do których '
        'stosuje się art. 28b ustawy – wykazana w K_27',
    )
    p_28 = fields.Integer(
        string='P_28',
        default=0,
        help='Zbiorcza wysokość podatku należnego z tytułu '
        'importu usług, zwyłączeniem usług nabywanych od '
        'podatników podatku od wartości dodanej, do których '
        'stosuje się art. 28b ustawy – wykazana w K_28',
    )
    p_29 = fields.Integer(
        string='P_29',
        default=0,
        help='Zbiorcza wysokość podstawy opodatkowania z tytułu '
        'importu usług nabywanych od podatników podatku od '
        'wartości dodanej, do których stosuje się art. 28b '
        'ustawy – wykazana w K_29',
    )
    p_30 = fields.Integer(
        string='P_30',
        default=0,
        help='Zbiorcza wysokość podatku należnego z tytułu '
        'importu usług nabywanych od podatników podatku od '
        'wartości dodanej, do których stosuje się art. 28b '
        'ustawy – wykazana w K_30',
    )
    p_31 = fields.Integer(
        string='P_31',
        default=0,
        help='Zbiorcza wysokość podstawy opodatkowania z tytułu '
        'dostawy towarów, dla których podatnikiem jest nabywca '
        'zgodnie z art. 17 ust. 1 pkt 5 ustawy – wykazana w K_31',
    )
    p_32 = fields.Integer(
        string='P_32',
        default=0,
        help='Zbiorcza wysokość podatku należnego z tytułu '
        'dostawy towarów, dla których podatnikiem jest nabywca '
        'zgodnie z art. 17 ust. 1 pkt 5 ustawy – wykazana w K_32',
    )
    p_33 = fields.Integer(
        string='P_33',
        default=0,
        help='Zbiorcza wysokość podatku należnego od towarów objętych '
        'spisem z natury, o którym mowa w art. 14 ust. 5 ustawy '
        '– wykazana w K_33',
    )
    p_34 = fields.Integer(
        string='P_34',
        default=0,
        help='Zbiorcza wysokość zwrotu odliczonej lub zwróconej kwoty '
        'wydanej na zakup kas rejestrujących, o którym mowa w '
        'art. 111 ust. 6 ustawy – wykazana w K_34',
    )
    p_35 = fields.Integer(
        string='P_35',
        default=0,
        help='Zbiorcza wysokość podatku należnego od '
        'wewnątrzwspólnotowego nabycia środków transportu, '
        'wykazana w wysokości podatku należnego z tytułu '
        'określonego w P_24, podlegająca wpłacie w terminie, '
        'o którym mowa w art. 103 ust. 3, w związku z ust. 4 '
        'ustawy – wykazana w K_35',
    )
    p_36 = fields.Integer(
        string='P_36',
        default=0,
        help='Zbiorcza wysokość podatku należnego od '
        'wewnątrzwspólnotowego nabycia towarów, o których mowa '
        'w art. 103 ust. 5aa ustawy, podlegająca wpłacie '
        'w terminach, o których mowa w art. 103 ust. 5a '
        'i 5b ustawy – wykazana w K_36',
    )
    p_37 = fields.Integer(
        string='P_37',
        readonly=True,
        compute='_compute_p37',
        help='Łączna wysokość podstawy opodatkowania. Suma kwot z P_10, P_11, P_13, P_15, P_17, '
        'P_19, P_21, P_22, P_23, P_25, P_27, P_29, P_31',
    )

    p_38 = fields.Integer(
        string='P_38',
        readonly=True,
        compute='_compute_p38',
        help='Łączna wysokość podatku należnego. Suma kwot z P_16, P_18, P_20, P_24, P_26, P_28, '
        'P_30, P_32, P_33, P_34 pomniejszona kwotę z P_35 i P_36',
    )

    p_39 = fields.Integer(
        string='P_39',
        default=0,
        help='Wysokość nadwyżki podatku naliczonego nad należnym '
        'z poprzedniej deklaracji (pole opcjonalne). '
        'Wykazuje się kwotę z P_62 z poprzedniej deklaracji '
        'lub kwotę wynikającą z decyzji.',
    )
    p_40 = fields.Integer(
        string='P_40',
        default=0,
        help='Zbiorcza wartość netto z tytułu nabycia towarów '
        'i usług zaliczanych upodatnika do środków trwałych '
        '– wykazana w K_40',
    )
    p_41 = fields.Integer(
        string='P_41',
        default=0,
        help='Zbiorcza wysokość podatku naliczonego z tytułu '
        'nabycia towarów i usług zaliczanych u podatnika '
        'do środków trwałych – wykazana w K_41',
    )
    p_42 = fields.Integer(
        string='P_42',
        default=0,
        help='Zbiorcza wartość netto z tytułu nabycia pozostałych ' 'towarów i usług – wykazana w K_42',
    )
    p_43 = fields.Integer(
        string='P_43',
        default=0,
        help='Zbiorcza wysokość podatku naliczonego z tytułu ' 'nabycia pozostałych towarów i usług – wykazana w K_43',
    )
    p_44 = fields.Integer(
        string='P_44',
        default=0,
        help='Zbiorcza wysokość podatku naliczonego z tytułu '
        'korekty podatku naliczonego od nabycia towarów i usług '
        'zaliczanych u podatnika do środków trwałych '
        '– wykazana w K_44',
    )
    p_45 = fields.Integer(
        string='P_45',
        default=0,
        help='Zbiorcza wysokość podatku naliczonego z tytułu '
        'korekty podatku naliczonego od nabycia pozostałych '
        'towarów i usług – wykazana w K_45',
    )
    p_46 = fields.Integer(
        string='P_46',
        default=0,
        help='Zbiorcza wysokość podatku naliczonego z tytułu korekty '
        'podatku naliczonego, o której mowa w art. 89b ust. 1 '
        'ustawy – wykazana w K_46',
    )
    p_47 = fields.Integer(
        string='P_47',
        default=0,
        help='Zbiorcza wysokość podatku naliczonego z tytułu '
        'korekty podatku naliczonego, o której mowa '
        'w art. 89b ust. 4 ustawy – wykazana w K_47',
    )
    p_48 = fields.Integer(
        string='P_48',
        readonly=True,
        compute='_compute_p48',
        help='Łączna wysokość podatku naliczonego do odliczenia. '
        'Suma kwot z P_39, P_41, P_43, P_44, P_45, P_46 i P_47',
    )

    p_49 = fields.Integer(
        string='P_49',
        default=0,
        help='Kwota wydana na zakup kas rejestrujących, do odliczenia '
        'w danym okresie rozliczeniowym pomniejszająca wysokość '
        'podatku należnego (pole opcjonalne). '
        'W przypadku wystąpienia nadwyżki podatku należnego nad '
        'naliczonym - w P_49 podaje się wysokość ulgi na zakup '
        'kas rejestrujących, w części przysługującej do '
        'odliczenia w danym okresie rozliczeniowym, '
        'do wysokości tej nadwyżki.',
    )

    p_50 = fields.Integer(
        string='P_50',
        default=0,
        help='Wysokość podatku objęta zaniechaniem poboru. '
        'Podaje się wysokość podatku objętą zaniechaniem poboru '
        'na podstawie art. 22 ustawy z dnia 29 sierpnia 1997 r. '
        '– Ordynacja podatkowa (Dz. U. z 2019 r. poz. 900, '
        'z późn. zm.), do wysokości nadwyżki podatku należnego '
        'nad naliczonym pomniejszonej o wysokość ulgi na zakup '
        'kas rejestrujących, do odliczenia w danym okresie '
        'rozliczeniowym.',
    )
    p_51 = fields.Integer(
        string='P_51',
        readonly=True,
        compute='_compute_p51',
        help='Wysokość podatku podlegająca wpłacie do urzędu skarbowego',
    )
    p_52 = fields.Integer(
        string='P_52',
        default=0,
        help='Kwota wydana na zakup kas rejestrujących, do odliczenia '
        'w danym okresie rozliczeniowym przysługująca do zwrotu '
        'w danym okresie rozliczeniowym lub powiększająca '
        'wysokość podatku naliczonego do przeniesienia na '
        'następny okres rozliczeniowy. W przypadku gdy wysokość '
        'podatku naliczonego jest większa lub równa wysokości '
        'podatku należnego w danym okresie rozliczeniowym lub '
        'wysokość ulgi na zakup kas rejestrujących jest większa '
        'od wysokości nadwyżki podatku należnego nad naliczonym '
        '– w P_52 podaje się pozostałą nieodliczoną w P_49 '
        'wysokość ulgi na zakup kas rejestrujących, '
        'przysługującą podatnikowi do zwrotu lub do '
        'odliczenia od podatku należnego za następne '
        'okresy rozliczeniowe.',
    )
    p_53 = fields.Integer(
        string='P_53',
        readonly=True,
        compute='_compute_p53',
        help='Wysokość nadwyżki podatku naliczonego nad należnym. Podaje się również podatek '
        'naliczony, który w związku z brakiem czynności opodatkowanych podlega przeniesieniu '
        'na następny okres rozliczeniowy lub zwrotowi. W tym polu podaje się także wysokość '
        'ulgi na zakup kas rejestrujących nieodliczoną od podatku należnego w danym okresie '
        'rozliczeniowym.',
    )
    p_54 = fields.Integer(
        string='P_54',
        default=0,
        help='Wysokość nadwyżki podatku naliczonego nad należnym do '
        'zwrotu na rachunek wskazany przez podatnika. '
        'Podaje się wysokość różnicy podatku podlegającą '
        'zwrotowi na rachunek bankowy podatnika oraz do '
        'zaliczenia na poczet przyszłych zobowiązań podatkowych.',
    )

    p_55_58 = fields.Selection(
        selection=[
            ('P_55', 'Zwrot na rachunek VAT, o którym mowa w art. 87 ust. 6a ustawy'),
            ('P_56', 'Zwrot w terminie 25 dni od dnia złożenia rozliczenia (art. 87 ust. 6 ustawy)'),
            ('P_57', 'Zwrot w terminie 60 dni od dnia złożenia rozliczenia (art. 87 ust. 2 ustawy)'),
            ('P_58', 'Zwrot w terminie 180 dni od dnia złożenia rozliczenia (art. 87 ust. 5a zdanie pierwsze ustawy)'),
        ],
        default='P_55',
    )

    p_59 = fields.Boolean(
        string='P_59',
        default=0,
        help='Zaliczenie zwrotu podatku na poczet przyszłych '
        'zobowiązań podatkowych. Podaje się „1” w przypadku '
        'wnioskowania przez podatnika o zaliczenie zwrotu '
        'podatku na poczet przyszłych zobowiązań podatkowych, '
        'zgodnie z art. 76 § 1 i art. 76b § 1 ustawy '
        'z dnia 29 sierpnia 1997 r. - Ordynacja podatkowa '
        '(Dz. U. z 2019 r. poz. 900, z późn. zm.).',
    )
    p_60 = fields.Integer(
        string='P_60',
        default=0,
        help='Wysokość zwrotu do zaliczenia na poczet przyszłych '
        'zobowiązań podatkowych. Podaje się wysokość zwrotu '
        'podatku do zaliczenia na poczet przyszłych '
        'zobowiązań podatkowych.',
    )
    p_61 = fields.Char(
        string='P_61',
        default=False,
        help='Rodzaj przyszłego zobowiązania podatkowego. '
        'Podaje się rodzaj przyszłego zobowiązania podatkowego, '
        'na poczet którego zalicza się zwrot podatku.',
    )
    p_62 = fields.Integer(
        string='P_62',
        readonly=True,
        compute='_compute_p62',
        help='Wysokość nadwyżki podatku naliczonego nad należnym do przeniesienia na następny ' 'okres rozliczeniowy.',
    )
    p_63 = fields.Boolean(
        string='P_63',
        default=False,
        help='Podatnik wykonywał w okresie rozliczeniowym czynności, '
        'o których mowa w art. 119 ustawy. '
        'Podaje się „1” w przypadku świadczenia usług turystyki '
        'opodatkowanych na zasadach marży.',
    )
    p_64 = fields.Boolean(
        string='P_64',
        default=False,
        help='Podatnik wykonywał w okresie rozliczeniowym czynności, '
        'o których mowa w art. 120 ust. 4 lub 5 ustawy. '
        'Podaje się „1” w przypadku dostawy towarów używanych, '
        'dzieł sztuki, przedmiotów kolekcjonerskich lub antyków '
        'nabytych uprzednio przez podatnika w ramach prowadzonej '
        'działalności gospodarczej, w celu odprzedaży, '
        'opodatkowanych na zasadach marży.',
    )
    p_65 = fields.Boolean(
        string='P_65',
        default=False,
        help='Podatnik wykonywał w okresie rozliczeniowym czynności, '
        'o których mowa w art. 122 ustawy. Podaje się „1” '
        'w przypadku wykonywania czynności polegających '
        'na dostawie, wewnątrzwspólnotowym nabyciu lub '
        'imporcie złota inwestycyjnego, zwolnionych od podatku '
        'zgodnie zart.122 ust. 1 ustawy, lub gdy podatnik, '
        'będąc agentem działającym w imieniu i na '
        'rzecz innych osób, pośredniczył w dostawie takiego '
        'złota dla swojego zleceniodawcy, zgodnie '
        'z art. 122 ust. 2 ustawy.',
    )
    p_66 = fields.Boolean(
        string='P_66',
        default=False,
        help='Podatnik wykonywał w okresie rozliczeniowym czynności, '
        'o których mowa w art. 136 ustawy. '
        'Podaje się „1” - w przypadku gdy podatnik, '
        'będąc drugim w kolejności podatnikiem VAT, '
        'dokonał transakcji trójstronnej '
        'w procedurze uproszczonej.',
    )
    p_67 = fields.Boolean(
        string='P_67',
        default=False,
        help='Podatnik korzysta z obniżenia zobowiązania podatkowego, '
        'o którym mowa w art. 108d ustawy. '
        'Podaje się „1” - w przypadku gdy podatnik korzystał '
        'z obniżenia zobowiązania podatkowego, jeżeli zapłaty '
        'zobowiązania podatkowego dokonuje w całości '
        'z rachunku VAT w terminie wcześniejszym '
        'niż termin zapłaty podatku.',
    )
    p_68 = fields.Integer(
        string='P_68',
        default=0,
        required=True,
        help='Zbiorcza wysokość korekty podstawy opodatkowania, o której mowa w art. 89a '
        'ust. 1 ustawy. Podaje się wysokość korekty podstawy opodatkowania, o której mowa '
        'w art. 89a ust. 1 ustawy, która została uwzględniona w pozycjach: K_15, K_17 i K_19.',
    )
    p_69 = fields.Integer(
        string='P_69',
        default=0,
        required=True,
        help='Zbiorcza wysokość korekty podatku należnego, o której mowa w art. 89a ust. 1 ustawy.'
        ' Podaje się wysokość korekty podatku należnego, o której mowa w art. 89a ust. 1 '
        'ustawy, która została uwzględniona w pozycjach: K_16, K_18 i K_20.',
    )
    p_ordzu = fields.Char(
        string='P_ORDZU', default=False, help='Uzasadnienie przyczyn złożenia korekty (pole fakultatywne).'
    )

    # V2 fields
    p_540 = fields.Boolean(string='P_540', help='Zwrot na rachunek rozliczeniowy podatnika w terminie 15 dni.')
    p_560 = fields.Boolean(string='P_560', help='Zwrot na rachunek rozliczeniowy podatnika w terminie 40 dni.')
    p_660 = fields.Boolean(
        string='P_660',
        help='Podatnik ułatwiał w okresie rozliczeniowym dokonanie czynności, o których mowa w '
        'art. 109b ust. 4 ustawy.',
    )

    source_xml = fields.Binary()

    is_jpk_transfer_installed = fields.Boolean(compute='_is_jpk_transfer_installed', store=False, readonly=True)

    @api.depends(*P_37_SUM_FIELDS)
    def _compute_p37(self):
        for rec in self:
            rec.p_37 = sum([rec[n] if rec[n] else 0 for n in P_37_SUM_FIELDS])

    @api.depends(*P_38_SUM_FIELDS)
    def _compute_p38(self):
        for rec in self:
            rec.p_38 = sum([rec[n] if rec[n] else 0 for n in P_38_PLUS_SUM_FIELDS]) - sum(
                [rec[n] if rec[n] else 0 for n in P_38_MINUS_SUM_FIELDS]
            )

    @api.depends(*P_48_SUM_FIELDS)
    def _compute_p48(self):
        for rec in self:
            rec.p_48 = sum([rec[n] if rec[n] else 0 for n in P_48_SUM_FIELDS])

    @api.depends('p_38', 'p_48', 'p_49', 'p_50')
    def _compute_p51(self):
        for rec in self:
            _sum = rec.p_38 - rec.p_48
            rec.p_51 = (_sum - rec.p_49 - rec.p_50) if _sum > 0 else 0

    @api.depends('version', 'p_38', 'p_48', 'p_49', 'p_51', 'p_50', 'p_52')
    def _compute_p53(self):
        for rec in self:
            if rec.version == '1-0E':
                # Jeżeli P_51 > 0 to P_53 = 0 w przeciwnym wypadku jeżeli (P_48 + P_49 + P_50  + P_52) – P_38 >  0
                # to P_53 = P_48 - P_38 + P_49 + P_50  + P_52 w pozostałych przypadkach P_53 = 0.
                if rec.p_51 > 0:
                    rec.p_53 = 0
                elif rec.p_48 + rec.p_49 + rec.p_50 + rec.p_52 - rec.p_38 >= 0:
                    rec.p_53 = rec.p_48 - rec.p_38 + rec.p_49 + rec.p_50 + rec.p_52
                else:
                    rec.p_53 = 0
            else:
                _sum = rec.p_48 - rec.p_38
                rec.p_53 = (_sum - +rec.p_52) if _sum >= 0 else 0

    @api.depends('p_53', 'p_54')
    def _compute_p62(self):
        for rec in self:
            rec.p_62 = rec.p_53 - rec.p_54

    @api.constrains('cel_zlozenia', 'czesc_deklaracyjna', 'czesc_ewidencyjna')
    def _check_correction(self):
        for record in self:
            if record.cel_zlozenia == 2 and not any([record.czesc_deklaracyjna, record.czesc_ewidencyjna]):
                raise ValidationError('Przynajmniej jedna sekcja musi być wskazana')

    # noinspection PyUnusedLocal
    def get_report_filename(self, options=None):
        return f'v7m_{self.month}_{self.year}{self.cel_zlozenia > 1 and "_korekta" or ""}'

    # noinspection HttpUrlsUsage
    # noinspection PyUnusedLocal
    def get_xml(self, options=None):
        tns = 'http://crd.gov.pl/wzor/2020/05/08/9393/'
        if self.version == '1-0E':
            tns = 'http://crd.gov.pl/wzor/2021/12/27/11148/'

        root = etree.fromstring(base64.b64decode(self.source_xml))

        is_correction = self.cel_zlozenia != 1
        is_section_deklaracja = not is_correction or self.czesc_deklaracyjna
        is_section_ewidencja = not is_correction or self.czesc_ewidencyjna

        if is_section_deklaracja:
            pozycje = root.xpath('tns:Deklaracja/tns:PozycjeSzczegolowe', namespaces={'tns': tns})

            if pozycje:
                pozycje = pozycje[0]
                pozycje.clear()
            else:
                deklaracja = root.xpath('tns:Deklaracja', namespaces={'tns': tns})[0]
                pozycje = etree.SubElement(deklaracja, etree.QName(tns, 'PozycjeSzczegolowe'))

            fields_def = self.fields_get()
            elements = {}

            for field in filter(lambda x: x.startswith('p_'), self.fields_get_keys()):
                # exceptions
                # skip p_54 to p_58 if p_54 is 0
                if field in ('p_54', 'p_55_58') and self.p_54 == 0:
                    continue

                # skip p_59 to p_61 if p_59 is not set
                if field in ('p_59', 'p_60', 'p_61') and not self.p_59:
                    continue

                value = self[field]
                field_type = fields_def[field]['type']
                if field_type == 'char':
                    if not value and value != '':
                        # skip
                        continue
                elif field_type == 'integer':
                    value = str(value)
                elif field_type == 'float':
                    value = float_repr(value, 2)
                elif field_type == 'selection':
                    if not value and value != '':
                        continue

                    field = value
                    value = '1'
                elif field_type == 'boolean':
                    if not value:
                        continue
                    value = '1'

                elements[field.upper()] = value

            for element, value in sorted(elements.items()):
                etree.SubElement(pozycje, etree.QName(tns, element)).text = value
        else:
            for deklaracja in root.xpath('tns:Deklaracja', namespaces={'tns': tns}):
                root.remove(deklaracja)

        if not is_section_ewidencja:
            for ewidencja in root.xpath('tns:Ewidencja', namespaces={'tns': tns}):
                root.remove(ewidencja)

        return etree.tostring(root, encoding='UTF-8', xml_declaration=True, pretty_print=True)

    def _is_jpk_transfer_installed(self):
        module = self.env['ir.module.module'].sudo().search([['name', '=', 'trilab_jpk_transfer']])
        self.is_jpk_transfer_installed = module and module.state == 'installed'

    def action_generate_xml(self):
        return {
            'type': 'ir_actions_account_report_download',
            'data': {'model': self._name, 'options': '{}', 'output_format': 'xml', 'financial_id': self.id},
        }

    def action_transfer_xml(self):
        document_type = 'trilab_jpk_base.jpk_v7m_1_2_doc_type'
        if self.version == '1-0E':
            document_type = 'trilab_jpk_base.jpk_v7m_1_0_doc_type'

        # noinspection PyUnresolvedReferences
        transfer_id = self.env['jpk.transfer'].create_with_document(
            {
                'name': f'JPK V7M {self.month}/{self.year}',
                'jpk_type': 'JPK',
                'file_name': f'jpk_vat_{self.month}_{self.year}.xml',
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
            # 'target': 'new'
        }

    # noinspection PyMethodMayBeStatic
    def action_cancel(self):
        # self.unlink()
        return {'type': 'ir.actions.act_window_close'}

    def action_generate_pdf(self):
        return self.env.ref('trilab_jpk_vat.report_jpk_vat_7m_pdf').report_action(self)
