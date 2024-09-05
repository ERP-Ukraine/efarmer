from odoo import _, fields, models


class VatDateExceptionConfirm(models.TransientModel):
    _name = "jpk.vat.date_exception"
    _description = "VAT Date exception wizard"

    message = fields.Text(
        string='Exception message',
        default=_(
            'The JPK date falls within an already closed JPK reporting period, '
            'potentially there will be a need to correct past JPK Declaration.\n'
            'Do you want to continue?'
        ),
    )

    def action_confirm(self):
        return (
            self.env['account.move']
            .browse(self._context.get('active_ids'))
            .with_context(x_check_jpk_lock_date=False)
            .action_post()
        )
