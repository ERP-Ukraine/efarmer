import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class KsefBatchImportWizard(models.TransientModel):
    _name = 'ksef.batch.import.wizard'
    _description = 'KSeF Batch Import Wizard'

    company_ids = fields.Many2many(
        'res.company',
        string='Companies',
        required=True,
        default=lambda self: self._default_company_ids(),
    )

    allowed_company_ids = fields.Many2many('res.company', compute='_compute_allowed_company_ids')

    date_from = fields.Datetime(
        string='Date From',
        default=lambda self: self._default_date_from(),
        required=True,
    )
    date_to = fields.Datetime(
        string='Date To',
        default=lambda self: self._default_date_to(),
        required=True,
    )

    @api.model
    def _default_company_ids(self):
        return self.env['account.edi.format']._x_ksef_get_invoice_batch_import_eligible_company_ids()

    @api.model
    def _default_date_from(self):
        return fields.Datetime.now() - timedelta(days=1)

    @api.model
    def _default_date_to(self):
        return fields.Datetime.now()

    @api.depends('company_ids')
    def _compute_allowed_company_ids(self):
        self.allowed_company_ids = self.env[
            'account.edi.format'
        ]._x_ksef_get_invoice_batch_import_eligible_company_ids()

    def action_start_batch_import(self):
        self.ensure_one()

        if not self.company_ids:
            raise UserError(_('Please select at least one company.'))

        self.env['account.edi.format']._x_ksef_start_invoice_batch_import(
            company_ids=self.company_ids,
            date_from=self.date_from,
            date_to=self.date_to,
        )

        self.env.ref('trilab_ksef.cron_check_invoice_batch_import_status')._trigger(
            at=fields.Datetime.now() + timedelta(minutes=1)
        )

        _logger.info(
            'KSeF batch import started for companies %s (date_from: %s, date_to: %s)',
            self.company_ids.ids,
            self.date_from,
            self.date_to,
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Batch Import Started'),
                'message': _(
                    'KSeF batch import has been started for %d company/companies. '
                    'The status check will run in 1 minute.',
                    len(self.company_ids),
                ),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
