# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, _
from odoo.exceptions import ValidationError

NO_CHANNEL_EXTERNAL_ID = 'no_channel'
NO_CHANNEL_NAME = 'No Channel'


class ExternalSaleChannel(models.Model):
    _name = 'external.sale.channel'
    _description = 'Sale Channel'

    _sql_constraints = [
        (
            'external_id_uniq',
            'unique (integration_id, external_id)',
            'External ID must be unique per integration',
        )
    ]

    integration_id = fields.Many2one(
        comodel_name='sale.integration',
        string='Sale Integration',
        ondelete='cascade',
    )

    external_id = fields.Char(
        string='External ID',
        required=True,
    )

    name = fields.Char(
        string='Name',
        required=True,
    )

    def create_or_update(self, external_id, name):
        """
            Get an existing sale channel or create a new one if it doesn't exist.
        """
        integration_id = self.env.context.get('default_integration_id')
        if not integration_id:
            raise ValidationError(_('Integration ID is required in the context.'))

        channel = self.get_record(integration_id, external_id, raise_error=False)

        if channel:
            channel.write({'name': name})
        else:
            channel_vals = {
                'external_id': external_id,
                'name': name,
                'integration_id': integration_id,
            }

            channel = self.create(channel_vals)

        return channel

    def get_record(self, integration_id, external_id, raise_error=True):
        """
            Get the sale channel record based on the external ID.
        """
        domain = [
            ('external_id', '=', external_id),
            ('integration_id', '=', integration_id),
        ]

        channel = self.search(domain, limit=1)
        if not channel and raise_error:
            raise ValidationError(_(
                f'We couldn\'t find the sales channel with ID {external_id} in your Shopify store.\n\n'
                f'To fix this:\n'
                f'\t1. Run an initial import: This will refresh the list of sales channels in your connector.\n'
                f'\t2. Check connector permissions: Make sure your connector has the "read_publications" '
                f'permission in Shopify. You can check and adjust permissions in the Quick Configuration '
                f'wizard within the connector\'s connection settings.\n\n'
                f'Need more help?\n'
                f'Learn more about adding permissions here: https://t.ly/NDWIw or contact our support '
                f'team: https://support.ventor.tech/'
            ))

        return channel

    def _ensure_no_channel_exists(self, integration_id):
        """
        Ensure 'No Channel' exists for the current integration.
        """
        no_channel = self.get_record(integration_id, NO_CHANNEL_EXTERNAL_ID, False)

        if not no_channel:
            no_channel = self.create({
                'external_id': NO_CHANNEL_EXTERNAL_ID,
                'name': NO_CHANNEL_NAME,
                'integration_id': integration_id,
            })

        return no_channel
