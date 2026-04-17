# See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class ExternalIntegrationTag(models.Model):
    _name = 'external.integration.tag'
    _description = 'External integration tag'
    _order = 'integration_id, name'

    name = fields.Char(
        string='Tag',
        required=True,
    )

    ttype = fields.Selection(
        selection=[
            ('order', 'Order'),
            ('product', 'Product'),
        ],
        string='Type',
        default='product',
        required=True,
    )

    integration_id = fields.Many2one(
        comodel_name='sale.integration',
        string='E-Commerce Store',
        ondelete='cascade',
        required=True,
    )

    external_language_id = fields.Many2one(
        comodel_name='integration.res.lang.external',
        string='External Language',
        domain='[("integration_id", "=", integration_id)]',
    )

    def _get_or_create_external_tag(
        self,
        name: str,
        ttype: str,
        integration_id: int,
        external_language_code: str = None,
        **kwargs,
    ):
        external_language_id = False
        if external_language_code:
            external_language_id = self.env['integration.res.lang.external'].search([
                ('code', '=', external_language_code),
                ('integration_id', '=', integration_id),
            ], limit=1).id or False

        domain = [
            ('ttype', '=', ttype),
            ('name', '=', name),
            ('integration_id', '=', integration_id),
            ('external_language_id', '=', external_language_id),
        ]

        record = self.search(domain, limit=1)
        if not record:
            record = self.create({
                'name': name,
                'ttype': ttype,
                'integration_id': integration_id,
                'external_language_id': external_language_id,
            })
        return record
