# See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, models, fields

_logger = logging.getLogger(__name__)

# How much of a log message reaches the server log below DEBUG. A single webhook
# payload is tens of kilobytes of pretty-printed JSON -- headers, every variant,
# every image -- and Odoo.sh blocks an instance whose odoo.log outgrows its disk
# quota. The full text is always kept on the integration.logging record, and is
# still emitted in full when this logger is set to DEBUG.
SERVER_LOG_MAX_CHARS = 400


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
            ('customer', 'Customers Sync'),
            ('order_import', 'Orders Import'),
        ],
        string='Event Type',
    )

    event_name = fields.Char(
        string='Event Name',
    )

    message = fields.Text(
        string='Message',
    )

    res_model = fields.Char(
        string='Related Model',
    )

    res_id = fields.Many2oneReference(
        string='Related Record',
        model_field='res_model',
    )

    @api.model
    def _format_for_server_log(self, message):
        """Shorten a message for the server log, unless DEBUG is on.

        The caller's message may be an entire webhook payload. Truncating it is
        what keeps odoo.log within the daily quota Odoo.sh enforces, but a silent
        truncation reads as "that was the whole payload", so say what was cut and
        where to get it.
        """
        if _logger.isEnabledFor(logging.DEBUG):
            return message

        text = message if isinstance(message, str) else str(message)
        if len(text) <= SERVER_LOG_MAX_CHARS:
            return text

        withheld = len(text) - SERVER_LOG_MAX_CHARS
        return (
            f'{text[:SERVER_LOG_MAX_CHARS]}... '
            f'[{withheld} more characters withheld; the full message is on the '
            f'Integration Log record, or raise this logger to DEBUG]'
        )

    @api.model
    def write_log(self, integration, event_type, event_name, message,
                  res_model=None, res_id=None, log_level='debug'):
        """
        Helper for writing integration logs.

        Args:
            integration: sale.integration record or id
            event_type: type of event (customers, webhook, etc.)
            event_name: short title
            message: detailed message
            res_model: optional model name of the related source record
            res_id: optional id of the related source record
            log_level: Python logging level name to use for the server log entry
                ('debug', 'info', 'warning', 'error'). Defaults to 'debug' so
                that routine customer-sync traces stay invisible at INFO level
                (e.g. Odoo.sh default). Pass 'info' for expected webhook events
                and 'error' for failures that should always be visible.
        """

        if not integration:
            return

        if isinstance(integration, int):
            integration = self.env['sale.integration'].browse(integration)

        # Always write to server log at the requested level, but only DEBUG gets
        # the message in full: see SERVER_LOG_MAX_CHARS.
        log_func = getattr(_logger, log_level, _logger.debug)
        log_func(
            '[Integration %s] %s: %s',
            integration.name,
            event_name,
            self._format_for_server_log(message),
        )

        if not integration._is_log_type_enabled(event_type):
            return

        vals = {
            'integration_id': integration.id,
            'event_type': event_type,
            'event_name': event_name,
            'message': message,
        }
        if res_model and res_id:
            vals['res_model'] = res_model
            vals['res_id'] = res_id

        self.sudo().create(vals)

        return True
