# See LICENSE file for full copyright and licensing details.

import logging

from odoo import models, fields


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
            _logger.warning(
                'Integration %s: %s (order=%s; external_id=%s; status=%s) processing failed: %s',
                self.integration_id.name,
                self._description,
                self.erp_order_id.name,
                self.external_str_id,
                self.internal_status,
                self.internal_info,
            )

        return result, ids

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
