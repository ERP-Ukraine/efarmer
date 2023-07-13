# Copyright 2023 VentorTech OU
# Part of Ventor modules. See LICENSE file for full copyright and licensing details.
from odoo import api, models, fields, _
from odoo.exceptions import UserError


class ProjectCapitalization(models.Model):
    _name = 'project.capitalization'
    _inherit = ['mail.thread']
    _description = 'Project Capitalization'
    _check_company_auto = True

    name = fields.Char(
        string='Name',
        default=lambda self: _('New'),
        copy=False,
        readonly=True,
    )

    state = fields.Selection(
        [('new', 'New'),
         ('in_progress', 'In Progress'),
         ('done', 'Done')],
        string='Status',
        required=True,
        default='new',
        tracking=True,
    )
    start_date = fields.Date(
        string='Start Date',
        required=True,
        default=fields.Date.context_today,
        tracking=True,
        states={
            'new': [('readonly', False)],
            'in_progress': [('readonly', False)],
            'done': [('readonly', True)]
        },
    )
    end_date = fields.Date(
        string='End Date',
        required=True,
        tracking=True,
        states={
            'new': [('readonly', False)],
            'in_progress': [('readonly', False)],
            'done': [('readonly', True)]
        },
    )
    company_id = fields.Many2one(
        'res.company',
        'Company',
        required=True,
        index=True,
        default=lambda self: self.env.company,
        states={
            'new': [('readonly', False)],
            'in_progress': [('readonly', False)],
            'done': [('readonly', True)]
        },
    )
    work_type_ids = fields.Many2many(
        comodel_name='youtrack.work.type',
        string='Work Types',
        required=True,
        states={
             'new': [('readonly', False)],
             'in_progress': [('readonly', False)],
             'done': [('readonly', True)]
        },
    )
    account_asset_counterpart_id = fields.Many2one(
        'account.account',
        string='Account Asset Counterpart',
        check_company=True,
        help="Account used as counterpart for entries related to this asset.",
        tracking=True,
        states={
            'new': [('readonly', False)],
            'in_progress': [('readonly', False)],
            'done': [('readonly', True)]
        },
    )
    capitalization_line_ids = fields.One2many(
        'project.capitalization.line',
        'capitalization_id',
        string='Capitalize To',
        states={
            'new': [('readonly', False)],
            'in_progress': [('readonly', False)],
            'done': [('readonly', True)]
        },
    )
    analytic_line_ids = fields.Many2many(
        'account.analytic.line',
        string='Analytic Line',
    )
    capitalization_date = fields.Date(
        string='Capitalization Date',
        required=True,
        tracking=True,
        states={
            'new': [('readonly', False)],
            'in_progress': [('readonly', False)],
            'done': [('readonly', True)]
        },
    )

    def generate_report(self):
        self.ensure_one()
        self.env['project.capitalization.line'].search([('capitalization_id', '=', self.id)]).unlink()
        domain = [
            ('date', '>=', self.start_date),
            ('date', '<=', self.end_date),
            ('task_product_id', '!=', False),
            ('is_capitalized', '=', False),
            ('work_type_id', 'in', self.work_type_ids.ids),
            ('is_timesheet', '=', True),
        ]
        analytic_lines = self.env['account.analytic.line'].search(domain)
        capitalized_lines = []
        task_product_ids = set(analytic_lines.mapped('task_product_id'))
        for task_product_id in task_product_ids:
            lines_by_task_product_id = analytic_lines.filtered(lambda line: line.task_product_id == task_product_id)
            account_asset_counterpart_ids = set(lines_by_task_product_id.mapped('account_asset_counterpart_id'))
            for account_asset_counterpart_id in account_asset_counterpart_ids:
                lines_by_account_asset_counterpart_id = lines_by_task_product_id.filtered(
                    lambda line: line.account_asset_counterpart_id == account_asset_counterpart_id)
                hours_spent = sum(lines_by_account_asset_counterpart_id.mapped('unit_amount'))
                amount = sum(lines_by_account_asset_counterpart_id.mapped('amount'))
                capitalized_lines.append((0, 0, {
                    'account_asset_counterpart_id': account_asset_counterpart_id.id,
                    'hours_spent': hours_spent,
                    'amount': abs(amount),
                    'capitalization_id': self.id,
                    'asset_id': task_product_id.id,
                }))

            lines_without_account_asset_counterpart_id = lines_by_task_product_id.filtered(
                lambda line: not line.account_asset_counterpart_id)
            if lines_without_account_asset_counterpart_id:
                hours_spent = sum(lines_without_account_asset_counterpart_id.mapped('unit_amount'))
                amount = sum(lines_without_account_asset_counterpart_id.mapped('amount'))
                capitalized_lines.append((0, 0, {
                    'account_asset_counterpart_id': False,
                    'hours_spent': hours_spent,
                    'amount': abs(amount),
                    'capitalization_id': self.id,
                    'asset_id': task_product_id.id,
                }))
        self.write({
            'analytic_line_ids': analytic_lines.ids,
            'capitalization_line_ids': capitalized_lines,
            'state': 'in_progress',
        })

    def capitalization(self):
        self.line_capitalize()
        lines = self.capitalization_line_ids

        for line in lines:
            value_residual = 0.00
            currency = line.currency_id
            original_value = currency._convert(line.amount, line.asset_id.currency_id, self.company_id, fields.Date.today())
            old_values = {
                'method_number': line.asset_id.method_number,
                'method_period': line.asset_id.method_period,
                'value_residual': line.asset_id.value_residual,
                'salvage_value': line.asset_id.salvage_value,
            }
            asset_vals = {
                'method_number': line.asset_id.method_number,
                'method_period': line.asset_id.method_period,
                'value_residual': value_residual,
                'salvage_value': original_value,
            }
            current_asset_book = line.asset_id.value_residual + line.asset_id.salvage_value
            increase = original_value - current_asset_book
            new_residual = min(current_asset_book - min(original_value, line.asset_id.salvage_value),
                               value_residual)
            new_salvage = min(current_asset_book - new_residual, original_value)
            residual_increase = max(0, value_residual - new_residual)
            salvage_increase = max(0, original_value - new_salvage)
            if line.asset_id.currency_id.round(residual_increase + salvage_increase) > 0:
                move = line.env['account.move'].create({
                    'ref': f"{self.name} {self.capitalization_date}",
                    'journal_id': line.asset_id.journal_id.id,
                    'date': self.capitalization_date,
                    'line_ids': [
                        (0, 0, {
                            'account_id': line.asset_id.account_asset_id.id,
                            'debit': residual_increase + salvage_increase,
                            'credit': 0,
                            'name': _('Value increase for: %(asset)s', asset=line.asset_id.name),
                        }),
                        (0, 0, {
                            'account_id': line.account_asset_counterpart_id.id,
                            'debit': 0,
                            'credit': residual_increase + salvage_increase,
                            'name': _('Value increase for: %(asset)s', asset=line.asset_id.name),
                        }),
                    ],
                })
                move._post()
                asset_increase = line.env['account.asset'].create({
                    'name': f"{self.name} {self.capitalization_date}",
                    'currency_id': line.asset_id.currency_id.id,
                    'company_id': line.asset_id.company_id.id,
                    'asset_type': line.asset_id.asset_type,
                    'method': line.asset_id.method,
                    'method_number': line.asset_id.method_number,
                    'method_period': line.asset_id.method_period,
                    'acquisition_date': self.capitalization_date,
                    'value_residual': residual_increase,
                    'salvage_value': salvage_increase,
                    'original_value': residual_increase + salvage_increase,
                    'account_asset_id': line.asset_id.account_asset_id.id,
                    'account_depreciation_id': line.asset_id.account_depreciation_id.id,
                    'account_depreciation_expense_id': line.asset_id.account_depreciation_expense_id.id,
                    'journal_id': line.asset_id.journal_id.id,
                    'parent_id': line.asset_id.id,
                    'original_move_line_ids': [
                        (6, 0, move.line_ids.filtered(lambda r: r.account_id == line.asset_id.account_asset_id).ids)],
                })
                asset_increase.validate()
                subject = _(
                    'A gross increase has been created') + ': <a href=# data-oe-model=account.asset data-oe-id=%d>%s</a>' % (
                          asset_increase.id, asset_increase.name)
                line.asset_id.message_post(body=subject)

            if increase < 0:
                if self.env['account.move'].search(
                        [('asset_id', '=', line.asset_id.id), ('state', '=', 'draft'), ('date', '<=', fields.Date.today())]):
                    raise UserError(
                        'There are unposted depreciations prior to the selected operation date, please deal with them first.')
                move = line.env['account.move'].create(line.env['account.move']._prepare_move_for_asset_depreciation({
                    'amount': -increase,
                    'asset_id': line.asset_id,
                    'move_ref': _('Value decrease for: %(asset)s', asset=line.asset_id.name),
                    'date': self.capitalization_date,
                    'asset_remaining_value': 0,
                    'asset_depreciated_value': 0,
                    'asset_value_change': True,
                }))._post()

            asset_vals.update({
                'value_residual': new_residual,
                'salvage_value': new_salvage,
            })
            line.asset_id.write(asset_vals)
            line.asset_id.compute_depreciation_board()
            line.asset_id.children_ids.write({
                'method_number': asset_vals['method_number'],
                'method_period': asset_vals['method_period'],
            })
            for child in line.asset_id.children_ids:
                child.compute_depreciation_board()
            tracked_fields = line.env['account.asset'].fields_get(old_values.keys())
            changes, tracking_value_ids = line.asset_id._mail_track(tracked_fields, old_values)
            if changes:
                line.asset_id.message_post(body=_('Depreciation board modified') + '<br>' + self.name,
                                           tracking_value_ids=tracking_value_ids)

        self.state = 'done'

    def line_capitalize(self):
        for capitalization in self:
            domain = [
                ('date', '>=', capitalization.start_date),
                ('date', '<=', capitalization.end_date),
                ('task_product_id', '!=', False),
                ('is_capitalized', '=', False),
                ('work_type_id', 'in', capitalization.work_type_ids.ids),
                ('is_timesheet', '=', True),
            ]
            capitalization.env['account.analytic.line'].search(domain).write({'is_capitalized': True})

    def open_analytic_lines(self):
        action = self.env.ref('hr_timesheet.timesheet_action_all').read()[0]
        action['domain'] = [('id', 'in', self.analytic_line_ids.ids)]
        action['context'] = {'group_by': ['task_product_id', 'account_asset_counterpart_id']}
        return action

    # def unlink(self):
    #     for line in self:
    #         if line.state == 'done':
    #             raise UserError(_('You cannot delete a locked Capitalization.'))
    #     return super(ProjectCapitalization, self).unlink()
    #
    # def write(self, vals):
    #     for line in self:
    #         if line.state == 'done':
    #             raise UserError(_('You cannot edit a locked Capitalization.'))
    #     return super(ProjectCapitalization, self).write(vals)

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('project.capitalization.sequence') or _('New')
        result = super(ProjectCapitalization, self).create(vals)
        return result
