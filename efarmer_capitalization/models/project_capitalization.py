# Copyright 2023 VentorTech OU
# Part of Ventor modules. See LICENSE file for full copyright and licensing details.
from odoo import models, fields, _
from odoo.exceptions import UserError


class ProjectCapitalization(models.Model):
    _name = 'project.capitalization'
    _description = 'Project Capitalization'
    _check_company_auto = True

    name = fields.Char(
        string='Name',
        default=lambda self: self.env['ir.sequence'].next_by_code('project.capitalization.sequence'),
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
            currency = line.currency_id
            original_value = currency._convert(line.amount, line.asset_id.currency_id, self.company_id, fields.Date.today())
            asset_child = line.asset_id.env['account.asset'].create({
                'parent_id': line.asset_id.id,
                'state': 'open',
                'name': f"{self.name} {fields.Date.today()}",
                'method_number': line.asset_id.method_number,
                'original_value': original_value,
                'journal_id': line.asset_id.journal_id.id,
                'account_asset_id': line.account_asset_counterpart_id.id,
                'account_depreciation_id': line.asset_id.account_depreciation_id.id,
                'account_depreciation_expense_id': line.asset_id.account_depreciation_expense_id.id,
            })
            asset_child.compute_depreciation_board()
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
        analytic_lines = self.env['account.analytic.line'].search([('id', 'in', self.analytic_line_ids.ids)])
        action = self.env.ref('analytic.account_analytic_line_action').read()[0]
        action['domain'] = [('id', 'in', analytic_lines.ids)]
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


class Task(models.Model):
    _inherit = 'project.task'

    asset_id = fields.Many2one(
        comodel_name='account.asset',
        string='Product',
    )
