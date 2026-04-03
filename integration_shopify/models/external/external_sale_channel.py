# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, _
from odoo.exceptions import ValidationError


NO_CHANNEL_NAME = 'No Channel'
NO_CHANNEL_EXTERNAL_ID = 'no_channel'


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
        string='E-Commerce Store',
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

    @property
    def is_no_channel(self) -> bool:
        self.ensure_one()
        return self.external_id == NO_CHANNEL_EXTERNAL_ID

    def create_or_update(self, integration_id: int, external_id: str, name: str) -> models.Model:
        record = self.get_record(integration_id, external_id, raise_error=False)

        if record:
            record.write({'name': name})
        else:
            record = self.create({
                'name': name,
                'external_id': external_id,
                'integration_id': integration_id,
            })

        return record

    def get_record(self, integration_id: int, external_id: str, raise_error: bool = True) -> models.Model:
        record = self.search([
            ('external_id', '=', external_id),
            ('integration_id', '=', integration_id),
        ], limit=1)

        if not record and raise_error:
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

        return record

    def _ensure_no_channel_exists(self, integration_id: int) -> models.Model:
        """
        Ensure 'No Channel' exists for the current integration.
        """
        record = self.get_record(integration_id, NO_CHANNEL_EXTERNAL_ID, False)

        if not record:
            record = self.create({
                'name': NO_CHANNEL_NAME,
                'external_id': NO_CHANNEL_EXTERNAL_ID,
                'integration_id': integration_id,
            })

        return record
