# Copyright 2023 VentorTech OU
# Part of Ventor modules. See LICENSE file for full copyright and licensing details.
from odoo import models, fields, _
from odoo.exceptions import UserError


class ProjectContractors(models.Model):
    _name = 'project.contractors'
    _description = 'Project Invoice B2B Contactors'
    _check_company_auto = True

    name = fields.Char(
        string='Name',
        default=lambda self: self.env['ir.sequence'].next_by_code('project.contractors.sequence'),
        # readonly=True,
    )

    state = fields.Selection(
        [('new', 'New'),
         ('in_progress', 'In Progress'),
         ('done', 'Paid')],
        string='Status',
        default='new',
        tracking=True,
    )
    start_date = fields.Date(
        string='Start Date',
        # required=True,
        default=fields.Date.context_today,
        tracking=True,
        # states={
        #     'new': [('readonly', False)],
        #     'in_progress': [('readonly', False)],
        #     'done': [('readonly', True)]
        # },
    )
    end_date = fields.Date(
        string='End Date',
        # required=True,
        tracking=True,
        # states={
        #     'new': [('readonly', False)],
        #     'in_progress': [('readonly', False)],
        #     'done': [('readonly', True)]
        # },
    )
    company_id = fields.Many2one(
        'res.company',
        'Company',
        # required=True,
        index=True,
        default=lambda self: self.env.company,
        # states={
        #     'new': [('readonly', False)],
        #     'in_progress': [('readonly', False)],
        #     'done': [('readonly', True)]
        # },
    )
    employee_id = fields.Many2one(comodel_name='hr.employee')

    employee_type = fields.Selection(
        related='employee_id.employee_type',
        string='Employee Type',
        store=True,
        readonly=False,
    )
    product_id = fields.Many2one('product.product', 'Product')


    # work_type_ids = fields.Many2many(
    #     comodel_name='youtrack.work.type',
    #     string='Work Types',
    #     required=True,
    #     states={
    #          'new': [('readonly', False)],
    #          'in_progress': [('readonly', False)],
    #          'done': [('readonly', True)]
    #     },
    # )
    # account_asset_counterpart_id = fields.Many2one(
    #     'account.account',
    #     string='Account Asset Counterpart',
    #     check_company=True,
    #     help="Account used as counterpart for entries related to this asset.",
    #     tracking=True,
    #     states={
    #         'new': [('readonly', False)],
    #         'in_progress': [('readonly', False)],
    #         'done': [('readonly', True)]
    #     },
    # )
    contractors_line_ids = fields.One2many(
        'project.contractors.line',
        'contractors_id',
        string='Contractors To',
        # states={
        #     'new': [('readonly', False)],
        #     'in_progress': [('readonly', False)],
        #     'done': [('readonly', True)]
        # },
    )
    analytic_line_ids = fields.Many2many(
        'account.analytic.line',
        string='Analytic Line',
    )

    def generate_report(self):
        self.ensure_one()
        self.env['project.contractors.line'].search([('contractors_id', '=', self.id)]).unlink()
        # domain = [
        #     ('date', '>=', self.start_date),
        #     ('date', '<=', self.end_date),
        #     ('is_paid', '=', False),
        #     ('employee_type', '=', self.employee_type),
        # ]
        analytic_lines = self.env['account.analytic.line'].search([])
        contractors_lines = []
        employee_ids = set(analytic_lines.mapped('employee_id'))
        for employee_id in employee_ids:
            lines_by_employee_ids = analytic_lines.filtered(lambda line: line.employee_id == employee_id)
            data_dict = {}
            for line in lines_by_employee_ids:
                hours_spent = line.unit_amount
                pay_rate = line.employee_id.pay_rate
                params = []
                if line.project_id.project_code:
                    params.append(line.project_id.project_code)
                if line.product_version_id.name:
                    params.append(line.product_version_id.name)
                if line.work_type_id.name:
                    params.append(line.work_type_id.name)
                if line.epic_id.name:
                    params.append(line.epic_id.name)
                if line.name_pl:
                    params.append('/' + line.name_pl)
                data = '. '.join(params)
                if data not in data_dict:
                    data_dict[data] = {
                        'employee_id': employee_id.id,
                        'description': data,
                        'hours_spent': hours_spent,
                        'pay_rate': pay_rate,
                        'bamboo_currency_id': line.employee_id.bamboo_currency_id.id,
                        'amount': pay_rate * hours_spent,
                        'contractors_id': self.id,
                    }
                else:
                    data_dict[data]['hours_spent'] += hours_spent
                    data_dict[data]['amount'] += pay_rate * hours_spent

            for data in data_dict.values():
                contractors_lines.append((0, 0, data))

        self.write({
            'analytic_line_ids': analytic_lines.ids,
            'contractors_line_ids': contractors_lines,
            'state': 'in_progress',
        })

    def generate_invoice(self):
        # self.line_is_paid()
        for contractor in self:
            vendor_bills = {}
            for line in contractor.contractors_line_ids:
                employee = line.employee_id
                if employee not in vendor_bills:
                    vendor_bills[employee] = {
                        'partner_id': employee.id,
                        'type': 'in_invoice',
                        'invoice_line_ids': [],
                    }
                vendor_bill = vendor_bills[employee]
                vendor_bill['invoice_line_ids'].append((0, 0, {
                    'name': line.description,
                    'quantity': line.hours_spent,
                    'price_unit': line.pay_rate,
                }))

            for vendor_bill_data in vendor_bills.values():
                vendor_bill = self.env['account.move'].create(vendor_bill_data)
                vendor_bill.action_post()

        # self.state = 'done'

    def line_is_paid(self):
        for contractors in self:
            contractors.env['account.analytic.line'].search([('id', 'in', self.analytic_line_ids.ids)]).write({'is_paid': True})

    def open_analytic_lines(self):
        analytic_lines = self.env['account.analytic.line'].search([('id', 'in', self.analytic_line_ids.ids)])
        action = self.env.ref('analytic.account_analytic_line_action').read()[0]
        action['domain'] = [('id', 'in', analytic_lines.ids)]
        action['context'] = {'group_by': ['employee_id', 'project_id', 'product_version_id', 'work_type_id', 'epic_id']}
        return action

    # def unlink(self):
    #     for line in self:
    #         if line.state == 'done':
    #             raise UserError(_('You cannot delete a locked Project Invoice B2B Contactors.'))
    #     return super(ProjectContractors, self).unlink()
    #
    # def write(self, vals):
    #     for line in self:
    #         if line.state == 'done':
    #             raise UserError(_('You cannot edit a locked Project Invoice B2B Contactors.'))
    #     return super(ProjectContractors, self).write(vals)

