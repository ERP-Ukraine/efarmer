# Copyright 2023 VentorTech OU
# Part of Ventor modules. See LICENSE file for full copyright and licensing details.
from odoo import models, fields

class DeliveryTerms(models.Model):
    _name = 'delivery.terms'
    _description = 'Delivery Terms'
    _check_company_auto = True

    name = fields.Char(string='Name', required=True)
    default_for_company = fields.Boolean(string='Default for the Company')
    company_id = fields.Many2one('res.company', 'Company', required=True, default=lambda self: self.env.company)
    description = fields.Text(string='Description on the Invoice')

    _sql_constraints = [
        ('unique_name_company',
         'UNIQUE(name, company_id)',
         'A delivery term with the same name for the same company already exists.'),
        ('unique_default_for_company',
         'UNIQUE(company_id, default_for_company)',
         'You can select only one default value for the company.'),
    ]
