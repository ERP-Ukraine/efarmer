# See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class IntegrationProductImageExternal(models.Model):
    _name = 'integration.product.image.external'
    _description = 'Integration Product Image External'

    integration_id = fields.Many2one(
        string='E-Commerce Store',
        comodel_name='sale.integration',
        required=True,
        ondelete='cascade',
    )

    code = fields.Char(
        string='Code',
        size=64,
    )

    name = fields.Char(
        string='External Name',
    )

    src = fields.Char(
        string='Src',
    )

    template_code = fields.Char(
        string='Template',
        size=16,
    )

    mapping_ids = fields.One2many(
        comodel_name='integration.product.image.mapping',
        inverse_name='external_image_id',
        string='Mappings',
    )

    @property
    def external_template(self):
        return self.env['integration.product.template.external'].search([
            ('integration_id', '=', self.integration_id.id),
            ('code', '=', self.template_code),
        ])

    def _compute_display_name(self):
        for rec in self:
            code = rec.code.rsplit('/', 1)[-1] if rec.code else False
            rec.display_name = f'(ID={rec.id}): {code}'

    def _create_image_mapping(self, **kwargs):
        self.ensure_one()
        return self.env['integration.product.image.mapping'].create({
            **kwargs,
            'external_image_id': self.id,
        })

    def _create_or_update_image_mapping_in(
        self,
        ttype: str = None,
        res_id: int = None,
        is_cover: bool = None,
        variant_code: str = None,
    ):
        self.ensure_one()

        mappings = self.mapping_ids.filtered(
            lambda x: x.in_pending
            and x.ttype == ttype
            and x.res_id == res_id
            and x.is_cover == is_cover
        )

        if variant_code:
            mappings = mappings.filtered(lambda x: x.variant_code == variant_code)
        else:
            mappings = mappings.filtered(lambda x: not x.variant_code)

        mapping = mappings[:1]

        if not mapping:
            mapping = self._create_image_mapping(
                ttype=ttype,
                res_id=res_id,
                is_cover=is_cover,
                variant_code=variant_code,
            )

        return mapping

    def action_open_mapping(self):
        self.ensure_one()
        mappings = self.mapping_ids

        return {
            'type': 'ir.actions.act_window',
            'name': mappings._description,
            'res_model': mappings._name,
            'view_mode': 'list',
            'domain': [('id', 'in', mappings.ids)],
            'target': 'current',
        }
