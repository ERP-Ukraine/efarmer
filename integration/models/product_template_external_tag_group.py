# See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields, _
from odoo.exceptions import ValidationError


class ProductTemplateExternalTagGroup(models.Model):
    _name = 'product.template.external.tag.group'
    _description = 'Product Template External Tag Group'

    integration_id = fields.Many2one(
        comodel_name='sale.integration',
        string='E-Commerce Store',
        required=True,
        ondelete='cascade',
    )

    integration_type_api = fields.Selection(
        related='integration_id.type_api',
        string='Integration Type',
    )

    product_tmpl_id = fields.Many2one(
        comodel_name='product.template',
        required=True,
        ondelete='cascade',
    )

    external_language_id = fields.Many2one(
        comodel_name='integration.res.lang.external',
        string='External Language',
        domain='[("integration_id", "=", integration_id)]',
    )

    tag_ids = fields.Many2many(
        comodel_name='external.integration.tag',
        string='Tags',
        relation='product_template_external_tag_group_tag_ids_rel',
        domain='[("id", "in", available_tag_ids)]',
    )

    available_tag_ids = fields.Many2many(
        comodel_name='external.integration.tag',
        string='Available Tags',
        compute='_compute_available_tag_ids',
        store=False,
    )

    @api.depends('integration_id', 'external_language_id')
    def _compute_available_tag_ids(self):
        for record in self:
            domain = [
                ('ttype', '=', 'product'),
            ]
            if record.integration_type_api == 'prestashop':
                domain.extend([
                    ('integration_id', '=', record.integration_id.id),
                    ('external_language_id', '=', record.external_language_id.id),
                ])
            records = self.env['external.integration.tag'].search(domain)
            record.available_tag_ids = [(6, 0, records.ids)]

    @api.constrains('product_tmpl_id', 'integration_id', 'external_language_id')
    def _check_unique_group(self):
        for record in self:
            domain = [
                ('id', '!=', record.id),
                ('product_tmpl_id', '=', record.product_tmpl_id.id),
                ('integration_id', '=', record.integration_id.id),
            ]
            if record.integration_type_api == 'prestashop':
                domain.append(('external_language_id', '=', record.external_language_id.id))

            if self.search_count(domain):
                raise ValidationError(_(
                    'A tag group for store "%(store)s" and language "%(language)s" already exists for this product.\n'
                    'Please add new tags to existing group instead (or remove it first).',
                    store=record.integration_id.name,
                    language=record.external_language_id.name or 'None',
                ))
