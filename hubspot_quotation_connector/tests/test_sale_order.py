# -*- coding: UTF-8 -*-
# Copyright 2023 Solvve, Inc. <sales@solvve.com>

import os
from odoo.tests import TransactionCase, tagged

# @tagged('--at_install', '-standard', 'hubspot')
# class TestSaleOrder(TransactionCase):
#     def setUp(self):
#         super(TestSaleOrder, self).setUp()
#         self.config = self.env['hubspot.config'].create({
#             'name': 'Test',
#             'access_token': os.getenv('TEST_HUBSPOT_ACCESS_TOKEN')
#         })
#         self.partner_id = self.env['res.partner'].create({
#             'name': 'Taras',
#             'email': 'sha@gmail.com'
#         })
