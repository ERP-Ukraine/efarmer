# See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class ExternalIntegrationTag(models.Model):
    _name = 'external.integration.tag'
    _description = 'External integration tag'

    name = fields.Char(
        string='Name',
        required=True,
    )
    integration_id = fields.Many2one(
        comodel_name='sale.integration',
        string='Sale Integration',
        ondelete='cascade',
    )

    def _get_or_create_tag_from_name(self, name):
        integration_id = self.env.context.get('default_integration_id', False)

        tag_id = self.search([
            ('name', '=', name),
            ('integration_id', '=', integration_id),
        ], limit=1)

        if not tag_id:
            vals = dict(name=name)
            tag_id = self.create(vals)

        return tag_id
