from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

from ..models.gus_regon import EntityType, ReportType


@tagged('trilab_pl_partners_sync', '-at_install', 'post_install')
class TestResPartner(TransactionCase):
    @classmethod
    def setUpClass(cls):
        """Set up data before all test method."""
        super(TestResPartner, cls).setUpClass()

        cls.pl_country_id: int = cls.env.ref('base.pl').id
        cls.company_state_id: int = cls.env['res.country.state'].search([('name', '=', 'zachodniopomorskie')]).id

        cls.company_id = cls.env['res.company'].create(
            {
                'name': 'Test Company',
                'x_pl_enable_gus': True,
                'x_pl_enable_krd': True,
                'country_id': cls.pl_country_id,
                'vat': '5342584136',
            }
        )
        cls.partner_pl = cls.env['res.partner'].create(
            {
                'name': 'Test Partner PL',
                'company_id': cls.company_id.id,
                'country_id': cls.pl_country_id,
                'vat': '8522570255',
            }
        )
        cls.partner_eu = cls.env['res.partner'].create(
            {'name': 'Test Partner EU', 'country_id': cls.env.ref('base.cz').id, 'vat': '12345679'}
        )
        cls.partner_contact = cls.env['res.partner'].create(
            {'name': 'Test Partner', 'country_id': cls.pl_country_id, 'pesel': '99051241166', 'is_company': False}
        )
        cls.partner_contact_fake = cls.env['res.partner'].create(
            {'name': 'Test Partner Fake', 'country_id': cls.pl_country_id, 'is_company': False}
        )

    def test_x_pl_check_vies_cron_valid(self):
        self.partner_pl.x_pl_check_vies_cron()
        self.assertTrue(self.partner_pl.x_pl_vies_state, 'valid')

    def test_x_pl_check_vies_cron_invalid(self):
        self.partner_eu.x_pl_check_vies_cron()
        self.assertNotEqual(self.partner_pl.x_pl_vies_state, 'valid')

    def test_x_pl_compute_country_flag_poland(self):
        self.partner_pl.x_compute_country_flag()
        self.assertTrue(self.partner_pl.x_pl_is_poland, True)

    def test_x_pl_compute_country_flag_europe(self):
        self.partner_eu.x_compute_enable_gus_krd()
        self.assertTrue(self.partner_eu.x_pl_is_europe, True)

    def test_x_pl_enable_gus_krd_valid(self):
        self.partner_eu.x_compute_country_flag()
        self.assertTrue(self.partner_pl.x_pl_enable_gus, True)
        self.assertTrue(self.partner_pl.x_pl_enable_krd, True)

    def test_x_pl_check_vies_without_errors(self):
        response = self.partner_pl.x_pl_check_vies()
        self.assertEqual(response.get(self.partner_pl.id, {}).get('error_type'), 'vies_ok')

    def test_x_pl_check_vies_with_errors(self):
        with self.assertRaises(ValidationError):
            self.partner_eu.x_pl_check_vies()

    def test_x_pl_constrains_pesel_valid(self):
        self.partner_contact.x_constrains_pesel()
        self.assertTrue(self.partner_contact.pesel)

    def test_x_pl_constrains_pesel_invalid(self):
        with self.assertRaises(ValidationError):
            self.partner_contact_fake.pesel = '12345678900'
            self.partner_contact_fake.x_constrains_pesel()

    def test_x_pl_parse_gus_data_valid(self):
        data = {
            'praw_nazwa': 'EPA MARINE SPÓŁKA Z OGRANICZONĄ ODPOWIEDZIALNOŚCIĄ',
            'praw_adSiedzUlica_Nazwa': 'ul. Mieszka I',
            'praw_adSiedzNumerNieruchomosci': '81',
            'praw_adSiedzNumerLokalu': None,
            'praw_adSiedzNietypoweMiejsceLokalizacji': None,
            'praw_adSiedzWojewodztwo_Nazwa': 'ZACHODNIOPOMORSKIE',
            'praw_adSiedzKodPocztowy': '71011',
            'praw_numerTelefonu': None,
            'praw_numerWewnetrznyTelefonu': None,
            'praw_adresEmail': None,
            'praw_adresStronyinternetowej': None,
            'praw_numerWRejestrzeEwidencji': '0000354821',
            'praw_adSiedzMiejscowosc_Nazwa': 'Szczecin',
        }
        company_type = EntityType('P')
        out = self.partner_pl._x_parse_gus_data(data, company_type, True)
        exp_out = {
            'x_pl_gus_update_date': fields.Date.today(),
            'x_pl_business_type': 'P',
            'lang': 'pl_PL',
            'country_id': self.pl_country_id,
            'state_id': self.company_state_id,
            'name': 'EPA MARINE SPÓŁKA Z OGRANICZONĄ ODPOWIEDZIALNOŚCIĄ',
            'street': 'ul. Mieszka I 81',
            'zip': '71-011',
            'krs': '0000354821',
            'city': 'Szczecin',
        }
        self.assertEqual(out, exp_out)

    def test_x_sanitize_nip_valid(self):
        nip = self.partner_pl.x_sanitize_nip(self.partner_pl.vat)
        self.assertEqual(nip, '8522570255')

    def test_validate_nip_valid(self):
        self.assertTrue(self.partner_pl.x_pl_validate_vat(vat=self.partner_pl.vat))

    def test_validate_nip_invalid(self):
        with self.assertRaises(ValidationError):
            self.partner_pl.x_pl_validate_vat(vat=None, raise_exception=True)
            self.partner_pl.x_pl_validate_vat(vat='', raise_exception=True)

    def test_get_report_valid(self):
        company_type = EntityType('P')
        out = self.partner_pl._x_get_gus_report_type(company_type, '6')
        exp_out = ReportType.OsPrawna
        self.assertEqual(out, exp_out)

    def test_add_fiz_key_to_gus_report_if_ceidg_not_ceidg(self):
        company_type = EntityType('P')
        report = self.partner_pl._x_get_gus_report_type(company_type, '6')
        data = {
            'praw_nazwa': 'EPA MARINE SPÓŁKA Z OGRANICZONĄ ODPOWIEDZIALNOŚCIĄ',
            'praw_adSiedzUlica_Nazwa': 'ul. Mieszka I',
            'praw_adSiedzNumerNieruchomosci': '81',
            'praw_adSiedzNumerLokalu': None,
            'praw_adSiedzNietypoweMiejsceLokalizacji': None,
            'praw_adSiedzWojewodztwo_Nazwa': 'ZACHODNIOPOMORSKIE',
            'praw_adSiedzKodPocztowy': '71011',
            'praw_numerTelefonu': None,
            'praw_numerWewnetrznyTelefonu': None,
            'praw_adresEmail': None,
            'praw_adresStronyinternetowej': None,
            'praw_numerWRejestrzeEwidencji': '0000354821',
            'praw_adSiedzMiejscowosc_Nazwa': 'Szczecin',
        }
        response = self.partner_pl._x_add_fiz_key_to_gus_report_if_ceidg(report, data)
        self.assertEqual(response, data)

    def test_x_pl_get_gus_data_valid(self):
        out = self.partner_pl._x_pl_get_gus_data(nip=self.partner_pl.vat, for_model=True)
        exp_out = [
            {
                'x_pl_gus_update_date': fields.Date.today(),
                'x_pl_business_type': 'P',
                'lang': 'pl_PL',
                'country_id': self.pl_country_id,
                'state_id': self.company_state_id,
                'name': 'EPA MARINE SPÓŁKA Z OGRANICZONĄ ODPOWIEDZIALNOŚCIĄ',
                'street': 'ul. Mieszka I 81',
                'zip': '71-011',
                'krs': '0000354821',
                'city': 'Szczecin',
                'regon': '320829015',
                'vat': '8522570255',
            }
        ]
        self.assertEqual(out, exp_out)

    def test_x_pl_update_gus_data_valid(self):
        out = self.partner_pl.x_pl_update_gus_data()
        exp_out = {
            self.partner_pl.id: {
                'error_type': 'gus_update',
                'error_message': 'Data successfully fetched from GUS',
                'records': [
                    {
                        'x_pl_gus_update_date': fields.Date.today(),
                        'x_pl_business_type': 'P',
                        'lang': 'pl_PL',
                        'country_id': self.pl_country_id,
                        'name': 'EPA MARINE SPÓŁKA Z OGRANICZONĄ ODPOWIEDZIALNOŚCIĄ',
                        'street': 'ul. Mieszka I 81',
                        'state_id': self.company_state_id,
                        'zip': '71-011',
                        'krs': '0000354821',
                        'city': 'Szczecin',
                        'regon': '320829015',
                        'vat': '8522570255',
                    }
                ],
            }
        }
        self.assertEqual(out, exp_out)

    def test_x_pl_update_gus_data_invalid(self):
        with self.assertRaises(ValidationError):
            self.partner_eu.x_pl_update_gus_data()

    def test_x_pl_check_mf_nip_valid(self):
        out = self.partner_pl.x_pl_check_mf_nip()
        exp_out = {}
        self.assertEqual(out, exp_out)

    def test_x_pl_check_mf_nip_invalid(self):
        with self.assertRaises(ValidationError):
            self.partner_eu.x_pl_check_mf_nip()

    def test_autocomplete_valid(self):
        out = self.partner_pl.x_gus_autocomplete('8522570255')
        exp_out = [
            {
                'x_pl_gus_update_date': fields.Date.today(),
                'x_pl_business_type': 'P',
                'lang': 'pl_PL',
                'country_id': {'id': self.pl_country_id, 'display_name': 'Poland'},
                'state_id': {'id': self.company_state_id, 'name': 'zachodniopomorskie'},
                'name': 'EPA MARINE SPÓŁKA Z OGRANICZONĄ ODPOWIEDZIALNOŚCIĄ',
                'street': 'ul. Mieszka I 81',
                'zip': '71-011',
                'krs': '0000354821',
                'city': 'Szczecin',
                'regon': '320829015',
                'vat': '8522570255',
            }
        ]
        self.assertEqual(out, exp_out)

    def test_x_pl_check_string_nip(self):
        out = self.partner_pl._x_pl_parse_vat('8522570255')
        exp_out = '8522570255'
        self.assertEqual(out, exp_out)

    def test_x_pl_check_string_invalid(self):
        out = self.partner_pl._x_pl_parse_vat('FAKENIP')
        exp_out = None
        self.assertEqual(out, exp_out)

    def test_x_pl_check_nip_valid(self):
        out = self.partner_pl.x_pl_validate_vat('8522570255')
        exp_out = '8522570255'
        self.assertEqual(out, exp_out)

    def test_x_pl_check_nip_invalid(self):
        out = self.partner_pl.x_pl_validate_vat('FAKENIP')
        exp_out = None
        self.assertEqual(out, exp_out)

    def test_x_pl_update_gus_action_valid(self):
        self.partner_pl.x_pl_update_gus_action()
        trilab_check_partner_details = self.env['trilab.check.partner.details'].search(
            [('partner_id', '=', self.partner_pl.id)], limit=1
        )
        self.assertTrue(trilab_check_partner_details.id)

    def test_x_pl_check_nip_action_valid(self):
        self.partner_pl.x_pl_check_nip_action()
        trilab_check_partner_details = self.env['trilab.check.partner.details'].search(
            [('partner_id', '=', self.partner_pl.id)], limit=1
        )
        self.assertTrue(trilab_check_partner_details.id)

    def test_x_pl_check_vies_action_valid(self):
        self.partner_pl.x_pl_check_vies_action()
        trilab_check_partner_details = self.env['trilab.check.partner.details'].search(
            [('partner_id', '=', self.partner_pl.id)], limit=1
        )
        self.assertTrue(trilab_check_partner_details.id)

    def test_x_pl_get_bank_accounts_valid(self):
        self.partner_pl.x_pl_get_bank_accounts()
        trilab_wl_wizard = self.env['trilab.wl.wizard'].search([('partner_id', '=', self.partner_pl.id)], limit=1)
        self.assertTrue(trilab_wl_wizard.id)
