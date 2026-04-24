# See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class IntegrationLogging(models.TransientModel):
    _name = 'integration.logging'
    _description = 'Integration Logs'
    _order = 'id DESC'
    _transient_max_hours = 24 * 30
    _rec_name = 'event_name'

    integration_id = fields.Many2one(
        comodel_name='sale.integration',
        string='E-Commerce Store',
    )

    event_type = fields.Selection(
        selection=[
            ('webhook', 'Webhook'),
        ],
        string='Event Type',
    )

    event_name = fields.Char(
        string='Event Name',
    )

    message = fields.Text(
        string='Message',
    )
