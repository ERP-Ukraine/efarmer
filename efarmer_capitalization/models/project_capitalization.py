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
        required=True,
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
        domain = [
            ('date', '>=', self.start_date),
            ('date', '<=', self.end_date),
            ('task_product_id', '!=', False),
            ('is_capitalized', '=', False),
            ('work_type_id', 'in', self.work_type_ids.ids),
            ('is_timesheet', '=', True),
        ]
        grouped_data = self.env['account.analytic.line'].read_group(
            domain,
            ['task_product_id', 'unit_amount', 'amount'],
            ['task_product_id'],
        )

        capitalized_lines = []
        analytic_line_ids = self.env['account.analytic.line'].search(domain)
        self.env['project.capitalization.line'].search([('capitalization_id', '=', self.id)]).unlink()
        for data in grouped_data:
            task_product_id = data['task_product_id'][0]
            hours_spent = data['unit_amount']
            amount = data['amount']
            capitalized_lines.append((0, 0, {
                'account_asset_counterpart_id': self.account_asset_counterpart_id.id,
                'hours_spent': hours_spent,
                'amount': abs(amount),
                'capitalization_id': self.id,
                'asset_id': task_product_id,
            }))
        self.write({
            'analytic_line_ids': analytic_line_ids,
            'capitalization_line_ids': capitalized_lines,
            'state': 'in_progress',
        })

    def capitalization(self):
        self.line_capitalize()
        lines = self.capitalization_line_ids
        for line in lines:
            asset_child = line.asset_id.env['account.asset'].create({
                'parent_id': line.asset_id.id,
                'state': 'open',
                'name': f"{self.name} {fields.Date.today()}",
                'method_number': line.asset_id.method_number,
                'original_value': line.amount,
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
        action['context'] = {'group_by': 'task_product_id'}
        return action

    def unlink(self):
        for line in self:
            if line.state == 'done':
                raise UserError(_('You cannot delete a locked Capitalization.'))
        return super(ProjectCapitalization, self).unlink()

    def write(self, vals):
        for line in self:
            if line.state == 'done':
                raise UserError(_('You cannot edit a locked Capitalization.'))
        return super(ProjectCapitalization, self).write(vals)


class Task(models.Model):
    _inherit = 'project.task'

    asset_id = fields.Many2one(
        comodel_name='account.asset',
        string='Product',
    )
