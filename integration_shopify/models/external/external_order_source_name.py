# See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class ExternalOrderSourceName(models.Model):
    _name = 'external.order.source.name'
    _description = 'Order Source Mapping'

    _sql_constraints = [
        (
            'external_name_uniq',
            'unique (integration_id, external_name)',
            'Order source names must be unique per integration',
        )
    ]

    integration_id = fields.Many2one(
        comodel_name='sale.integration',
        string='E-Commerce Integration',
        ondelete='cascade',
        help='Associated e-commerce platform integration',
    )

    external_name = fields.Char(
        string='External Source Name',
        required=True,
        help='Order source identifier from the external system (e.g., "web", "mobile_app", "pos")',
    )

    name = fields.Char(
        string='Source Name',
        required=True,
        help='User-friendly name for this order source in Odoo',
    )

    def get_or_create(self, integration_id, external_name, name=None):
        """
        Retrieve or create an Order Source Name record.

        Args:
            integration_id: ID of the related integration
            external_name: External identifier for the order source
            name: Optional display name (defaults to external_name)

        Returns:
            recordset: Single record that was found or created

        Raises:
            ValueError: If external_name is not provided
        """
        if not external_name:
            raise ValueError('External source name must be provided to create or retrieve a record.')

        name = name or external_name

        domain = [
            ('integration_id', '=', integration_id),
            ('external_name', '=', external_name)
        ]

        record = self.search(domain, limit=1)
        if record:
            return record

        return self.create({
            'integration_id': integration_id,
            'external_name': external_name,
            'name': name,
        })
