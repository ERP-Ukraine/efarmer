from odoo import fields, models


class MoveResequence(models.TransientModel):
    _name = 'trilab_jpk_base.move_resequence'
    _description = 'Trilab JPK Base Move Resequence Wizard'

    year = fields.Selection(
        lambda self: [
            (str(year), str(year)) for year in range(fields.Date.today().year, fields.Date.today().year - 50, -1)
        ],
        'Year',
        required=True,
        default=lambda self: str(fields.Date.today().year),
    )
    journal_ids = fields.Many2many(
        'account.journal',
        string='Journals',
        required=True,
        default=lambda self: self.journal_ids.search([]),
    )

    def action_resequence_entries(self):
        self.ensure_one()

        if move_ids := self.env['account.move'].search(
            [
                ('date', '>=', f'{self.year}-01-01'),
                ('date', '<=', f'{self.year}-12-31'),
                ('journal_id', 'in', self.journal_ids.ids),
            ],
            order='date, id',
        ):
            move_ids.x_journal_entry_number = False
            move_ids.flush_recordset(['x_journal_entry_number'])

            for journal_id, move_ids in (
                move_ids.filtered(lambda m_id: m_id.state == 'posted').grouped(lambda m_id: m_id.journal_id).items()
            ):
                seq_prefix = f'{journal_id.type}/{journal_id.id}/{self.year}/'

                for idx, move_id in enumerate(move_ids, start=1):
                    move_id.x_journal_entry_number = f'{seq_prefix}{idx}'
