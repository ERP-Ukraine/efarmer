# -*- coding: UTF-8 -*-
# Copyright 2023 Solvve, Inc. <sales@solvve.com>

import os
from odoo.tests import TransactionCase, tagged


@tagged('--at_install', '-standard', 'hubspot')
class TestHubSpotConfig(TransactionCase):
    def setUp(self):
        super(TestHubSpotConfig, self).setUp()
        self.config = self.env['hubspot.config'].create({
            'name': 'Test',
            'access_token': os.getenv('TEST_HUBSPOT_ACCESS_TOKEN')
        })
        self.partner_id = self.env['res.partner'].create({
            'name': 'Taras',
            'email': 'gemini.furniture39@example.com'
        })

    def test_get_contact_by_email(self):
        response = self.config.get_contact_by_email(self.partner_id.email)
        self.assertEqual(type(response), list)

    def test_get_deals_by_partner(self):
        response = self.config.get_deals_by_partner(self.partner_id)
        self.assertEqual(type(response), list)
