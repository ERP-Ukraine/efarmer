from odoo import api, fields, models


class BankRecWidget(models.Model):
    _inherit = 'bank.rec.widget'

    x_show_post_move_btn = fields.Boolean(compute='_x_compute_show_post_move_btn')

    @api.depends('st_line_id')
    def _x_compute_show_post_move_btn(self):
        for wizard_id in self:
            wizard_id.x_show_post_move_btn = (
                wizard_id.st_line_id.journal_id.x_cash_valuation_method and wizard_id.move_id.state == 'draft'
            )

    @api.depends('st_line_id')
    def _compute_state(self):
        super()._compute_state()

        for wizard_id in self:
            if wizard_id.st_line_id.journal_id.x_cash_valuation_method and wizard_id.move_id.state == 'draft':
                wizard_id.state = 'invalid'

    def _js_action_x_post_move(self):
        with self._action_validate_method():
            self._x_action_post_move()

    def _x_action_post_move(self):
        self.ensure_one()

        line_ids_create_command_list = []

        self._validation_lines_vals(line_ids_create_command_list, {}, [])

        st_line_id = self.st_line_id
        move_id = st_line_id.move_id.with_context(
            force_delete=True,
            skip_readonly_check=True,
        )
        move_id.write({'line_ids': [fields.Command.clear()] + line_ids_create_command_list})

        move_id.checked = True
        move_id.action_post()
