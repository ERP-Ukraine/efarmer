# See LICENSE file for full copyright and licensing details.

from odoo.tests import Form, TransactionCase, tagged


@tagged('post_install', '-at_install', 'test_res_partner_form')
class TestResPartnerForm(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.parent = cls.env['res.partner'].create({'name': 'Parent Company', 'is_company': True})

    def _is_invisible(self, form):
        return bool(form._get_modifier('external_company_name', 'invisible'))

    def test_field_is_hidden_in_the_dialog_creating_a_child_contact(self):
        with Form(self.parent) as parent_form:
            with parent_form.child_ids.new() as child_form:
                self.assertTrue(self._is_invisible(child_form))
                child_form.name = 'Manual Contact'

    def test_field_is_shown_for_an_address_with_a_company_name(self):
        child = self.env['res.partner'].create({
            'name': 'Imported Address',
            'type': 'invoice',
            'parent_id': self.parent.id,
            'external_company_name': 'Müllers Company',
        })

        with Form(self.parent) as parent_form:
            with parent_form.child_ids.edit(0) as child_form:
                self.assertEqual(child_form.name, child.name)
                self.assertFalse(self._is_invisible(child_form))
                self.assertEqual(child_form.external_company_name, 'Müllers Company')

    def test_field_is_hidden_for_an_address_without_a_company_name(self):
        self.env['res.partner'].create({
            'name': 'Manual Address',
            'type': 'delivery',
            'parent_id': self.parent.id,
        })

        with Form(self.parent) as parent_form:
            with parent_form.child_ids.edit(0) as child_form:
                self.assertTrue(self._is_invisible(child_form))

    def test_main_form_behaviour_is_unchanged(self):
        with Form(self.parent) as form:
            self.assertTrue(self._is_invisible(form))

        self.parent.external_company_name = 'Shop Company'

        with Form(self.parent) as form:
            self.assertFalse(self._is_invisible(form))
