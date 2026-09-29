# See LICENSE file for full copyright and licensing details.

import logging

from odoo import models, fields, _
from odoo.exceptions import UserError


_logger = logging.getLogger(__name__)


class ExternalOrderResource(models.AbstractModel):
    _name = 'external.order.resource'
    _description = 'External Order Resource'

    name = fields.Char(
        string='Resource Name',
        help='Name / Identifier for this External Resource',
    )
    internal_status = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('skipped', 'Skipped'),
            ('failed', 'Failed'),
            ('done', 'Done'),
        ],
        string='Processing Status',
        default='draft',
        required=True,
        help='Current processing status of this resource in Odoo',
    )
    external_str_id = fields.Char(
        string='External Resource ID',
        help='Unique identifier from the external system (e.g., Shopify, WooCommerce)',
    )
    external_order_str_id = fields.Char(
        string='External Order ID',
        help='Order identifier from the external e-commerce system',
    )
    # FIXME: external_status is a Char, which prevents using Selection-based
    # widgets (badge, statusbar) in views. Child models should define their own
    # `state` Selection field instead (see external.order.return and
    # external.order.fulfillment for examples). This field is kept for
    # backward compatibility but should be phased out in favor of per-model
    # `state` fields with properly typed selections.
    external_status = fields.Char(
        string='External System Status',
        help='Current status as reported by the external e-commerce system',
    )
    internal_info = fields.Char(
        string='Processing Information',
        help='Additional information about the processing status or any errors encountered',
    )
    erp_order_id = fields.Many2one(
        comodel_name='sale.order',
        string='Sales Order',
        ondelete='cascade',
        help='Associated Odoo sales order',
    )
    integration_id = fields.Many2one(
        related='erp_order_id.integration_id',
        string='E-Commerce Integration',
        help='E-commerce platform integration configuration',
    )
    integration_name = fields.Char(
        string='Platform Name',
        related='integration_id.name',
        help='Name of the e-commerce platform (e.g., Shopify, WooCommerce)',
    )
    is_ecommerce_ok = fields.Boolean(
        string='External Status Valid',
        compute='_compute_is_ecommerce_ok',
        help='Indicates if the external status allows processing in Odoo',
    )

    @property
    def is_done(self):
        return self.internal_status == 'done'

    @property
    def is_external_failed(self):
        return self.is_ecommerce_ok and self.internal_status == 'failed'

    def _compute_is_ecommerce_ok(self):
        for rec in self:
            rec.is_ecommerce_ok = False

    def mark_done(self):
        """Mark the resource as successfully processed"""
        self.write({'internal_status': 'done'})

    def mark_skipped(self):
        """Mark the resource as skipped (not applicable)"""
        self.write({'internal_status': 'skipped'})

    def mark_failed(self):
        """Mark the resource as failed during processing"""
        self.write({'internal_status': 'failed'})

    def action_skip(self):
        """Merchant-driven escape hatch: mark this external record as skipped
        so the connector ignores it from now on.

        Use cases: a refund was handled manually outside Odoo, a transaction
        duplicates a manually-recorded payment, or a return no longer applies
        because the merchant adjusted the order another way. Skipped records
        do not participate in dispatch and do not block outgoing-picking
        validation (the pre-fulfillment safety net on `sale.order`).

        Refused on already-processed records — skipping a `done` record is a
        logic error, not a no-op.
        """
        for record in self:
            if record.internal_status == 'done':
                raise UserError(_(
                    'Cannot skip %(name)s: this record has already been '
                    'processed (status: done).',
                    name=record.display_name,
                ))
            record.internal_status = 'skipped'
            record.internal_info = _(
                'Skipped by %(user)s on %(date)s.',
                user=self.env.user.display_name,
                date=fields.Datetime.now(),
            )
            # External record models don't inherit mail.thread, so the audit
            # message lands on the parent sale order (which does carry the
            # chatter). Order is always present for resources reached from
            # the form views where the Skip button is exposed.
            if record.erp_order_id:
                record.erp_order_id.message_post(body=_(
                    '%(description)s "%(name)s" marked as skipped by '
                    '%(user)s. The connector will ignore it.',
                    description=record._description,
                    name=record.display_name,
                    user=self.env.user.display_name,
                ))
            _logger.info(
                '%s %s marked as skipped by user %s (order=%s)',
                record._description,
                record.external_str_id or record.display_name,
                self.env.user.login,
                record.erp_order_id.name if record.erp_order_id else '',
            )

        title = _('Skip')

        if len(self) == 1:
            message = _('%s marked as skipped. The connector will ignore it from now on.') % self._description
        else:
            message = _('%s records marked as skipped. The connector will ignore them from now on.') % len(self)

        return self.display_integration_notification(message, title=title)

    def _get_or_create_from_external(self, data):
        """
        Get existing record or create new one from external data

        Args:
            data (dict): External data dictionary

        Returns:
            record: Found or newly created record
        """
        record = self.search([
            ('external_str_id', '=', data['external_str_id']),
            ('integration_id', '=', self.env.context.get('integration_id', False)),
        ], limit=1)

        data['external_order_str_id'] = self.env.context.get('external_order_id')
        # Pre-bind the new record to its sale.order when the caller supplies
        # erp_order_id via context (returns / refunds need this so the related
        # integration_id resolves before later integration_id-filtered searches
        # run, e.g. linked_return_str_id resolution inside the refund flow).
        if self.env.context.get('erp_order_id') and not data.get('erp_order_id'):
            data['erp_order_id'] = self.env.context.get('erp_order_id')

        vals = self._prepare_vals_from_external(data)

        if not record:
            record = self.create(vals)
        else:
            record.write(vals)

        return record

    def validate(self):
        """
        Validate and process the external resource

        Returns:
            tuple: (success, record_ids)
        """
        result, ids = self._validate()

        if not result:
            self._log_processing_failed()

        return result, ids

    def action_validate(self):
        """Button entry point for `validate`: validate and show a confirmation toast.

        Sets `integration_force_validate` so `_validate()` also processes records the
        merchant skipped. Automatic dispatch calls `validate()` directly and never sets it.
        """
        result, _ids = self.with_context(integration_force_validate=True).validate()
        title = _('Apply')

        if not result:
            return self.display_integration_notification(_('Validation failed.'), title=title, ttype='warning')

        return self.display_integration_notification(_('Validated successfully.'), title=title)

    def _validate(self):
        """
        Implement validation logic in child classes

        Returns:
            tuple: (success, record_ids)
        """
        raise NotImplementedError

    def _prepare_vals_from_external(self, data: dict) -> dict:
        """
        Prepare values for creating/updating records from external data

        Args:
            data (dict): Raw external data

        Returns:
            dict: Prepared values for Odoo record
        """
        return data

    def _log_processing_failed(self):
        _logger.warning(
            'Integration %s: %s (order=%s; external_id=%s; status=%s) processing failed: %s',
            self.integration_id.name,
            self._description,
            self.erp_order_id.name,
            self.external_str_id,
            self.internal_status,
            self.internal_info,
        )
