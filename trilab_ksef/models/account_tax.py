from odoo import api, fields, models

KSEF_TAX_AMOUNT_MAP = {
    23: ('23', '23%'),
    22: ('22', '22%'),
    8: ('8', '8%'),
    7: ('7', '7%'),
    5: ('5', '5%'),
    4: ('4', '4%'),
    3: ('3', '3%'),
}


class AccountTax(models.Model):
    _inherit = 'account.tax'

    x_ksef_amount = fields.Selection(
        string='KSeF Tax Amount Mapping',
        selection=[
            *KSEF_TAX_AMOUNT_MAP.values(),
            ('0 KR', '0% KR'),
            ('0 WDT', '0% WDT'),
            ('0 EX', '0% EX'),
            ('zw', 'ZW'),
            ('oo', 'OO'),
            ('np I', 'NP I'),
            ('np II', 'NP II'),
        ],
        compute='_x_ksef_compute_amount',
        store=True,
        help="""* 0% KR - Stawka 0% w przypadku sprzedaży towarów i świadczenia usług na terytorium kraju (z wyłączeniem WDT i eksportu)
        * 0% WDT - Stawka 0% w przypadku wewnątrzwspólnotowej dostawy towarów (WDT)
        * 0% EX - Stawka 0% w przypadku eksportu towarów
        * ZW - Zwolnione od podatku
        * OO - Odwrotne obciążenie
        * NP I - niepodlegające opodatkowaniu- dostawy towarów oraz świadczenia usług poza terytorium kraju, z wyłączeniem transakcji, o których mowa w art. 100 ust. 1 pkt 4 ustawy oraz OSS
        * NP II - niepodlegające opodatkowaniu na terytorium kraju, świadczenie usług o których mowa w art. 100 ust. 1 pkt 4 ustawy
        """,
    )

    @api.depends('amount', 'amount_type')
    def _x_ksef_compute_amount(self):
        for tax_id in self:
            if tax_id.amount_type != 'percent' or not (ksef_tax_amount := KSEF_TAX_AMOUNT_MAP.get(int(tax_id.amount))):
                tax_id.x_ksef_amount = None
                continue

            tax_id.x_ksef_amount = ksef_tax_amount[0]
