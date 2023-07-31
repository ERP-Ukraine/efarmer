# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import fields, models, api


class ProductFunction(models.Model):
    _name = "product.function"
    _description = "Product Function"
    _parent_name = "parent_id"
    _parent_store = True
    _rec_name = 'complete_name'
    _order = 'complete_name'

    name = fields.Char('Name', index=True, required=True)
    complete_name = fields.Char('Complete Name', compute='_compute_complete_name', store=True)
    parent_id = fields.Many2one('product.function', 'Parent Function', index=True, ondelete='cascade')

    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        for product_func in self:
            if product_func.parent_id:
                product_func.complete_name = '%s / %s' % (product_func.parent_id.complete_name, product_func.name)
            else:
                product_func.complete_name = product_func.name
