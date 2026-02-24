from odoo import api, models, fields
from odoo.exceptions import UserError
from odoo.tools import config


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    description_label = fields.Text(
        string='Description for Product Labels',
        compute='_compute_description_label',
        inverse='_set_description_label',
        store=True,
        translate=True,
    )

    @api.depends('product_variant_ids', 'product_variant_ids.description_label')
    def _compute_description_label(self):
        unique_variants = self.filtered(lambda template: len(template.product_variant_ids) == 1)
        for record in unique_variants:
            translations = self.env['ir.translation'].search([
                ('name', '=', 'product.product,description_label'),
                ('type', '=', 'model'),
                ('res_id', '=', record.product_variant_ids[:1].id),
                ('state', '=', 'translated'),
            ])
            for translation in translations:
                record.with_context(lang=translation.lang).description_label = translation.value

    def _set_description_label(self):
        for template in self:
            if len(template.product_variant_ids) == 1:
                translations = self.env['ir.translation'].search([
                    ('name', '=', 'product.template,description_label'),
                    ('type', '=', 'model'),
                    ('res_id', '=', template.id),
                    ('state', '=', 'translated'),
                ])
                for translation in translations:
                    template.product_variant_ids.with_context(lang=translation.lang).description_label = translation.value

    @api.model
    def create(self, vals):
        group_name = 'efarmer_sale_workflow.efarmer_sale_workflow_group_prod_categ_creator'
        if not self.env.user.has_group(group_name):
            # do not break odoo test
            if not config['test_enable'] and not config['test_file']:
                raise UserError("You're not allowed to create a product.")

        return super().create(vals)
