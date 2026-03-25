# See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class ExternalBusinessEntity(models.Model):
    _name = 'external.business.entity'
    _description = 'Merchant Business Entity'

    integration_id = fields.Many2one(
        comodel_name='sale.integration',
        string='E-Commerce Store',
        ondelete='cascade',
        required=True,
    )

    external_id = fields.Char(
        string='External ID',
        required=True,
    )

    name = fields.Char(
        string='Name',
        required=True,
    )

    def create_or_update(self, integration_id: int, external_id: str, name: str) -> models.Model:
        record = self.search([
            ('external_id', '=', external_id),
            ('integration_id', '=', integration_id),
        ], limit=1)

        if record:
            record.write({'name': name})
        else:
            record = self.create({
                'name': name,
                'external_id': external_id,
                'integration_id': integration_id,
            })

        return record
