# Copyright 2023 VentorTech OU
# Part of Ventor modules. See LICENSE file for full copyright and licensing details.
from odoo import api, models, fields, _
from functools import reduce
from odoo.exceptions import UserError


class ProjectContractors(models.Model):
    _name = 'project.contractors'
    _inherit = ['mail.thread']
    _description = 'Project Invoice B2B Contactors'
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
         ('done', 'Paid')],
        string='Status',
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
            'in_progress': [('readonly', True)],
            'done': [('readonly', True)]
        },
    )
    end_date = fields.Date(
        string='End Date',
        required=True,
        tracking=True,
        states={
            'new': [('readonly', False)],
            'in_progress': [('readonly', True)],
            'done': [('readonly', True)]
        },
    )
    company_id = fields.Many2one(
        'res.company',
        'Company',
        default=lambda self: self.env.company,
        states={
            'new': [('readonly', False)],
            'in_progress': [('readonly', True)],
            'done': [('readonly', True)]
        },
    )
    employee_id = fields.Many2one(comodel_name='hr.employee')
    employee_type = fields.Selection(
        related='employee_id.employee_type',
        string='Employee Type',
        store=True,
        readonly=False,
    )
    product_id = fields.Many2one('product.product', 'Product')

    contractors_line_ids = fields.One2many(
        'project.contractors.line',
        'contractors_id',
        string='Contractors To',
        states={
            'new': [('readonly', False)],
            'in_progress': [('readonly', True)],
            'done': [('readonly', True)]
        },
    )
    analytic_line_ids = fields.Many2many(
        'account.analytic.line',
        string='Analytic Line',
    )
    account_move_ids = fields.Many2many(
        'account.move',
        string='Vendor Bills',
    )

    is_paid = fields.Boolean(
        string='Is Paid?',
        compute='_compute_is_paid',
    )
    is_generate = fields.Boolean(
        string='Is Generate',
        compute='_compute_is_generate',
    )

    def _compute_is_generate(self):
        for rec in self:
            is_generate = False
            if rec.contractors_line_ids:
                is_generate = True
            rec.is_generate = is_generate

    def _compute_is_paid(self):
        for rec in self:
            is_paid = False
            if rec.account_move_ids and rec.state != 'done':
                if all(o.state == 'posted' for o in rec.account_move_ids):
                    is_paid = True
                    rec.write({
                        'state': 'done',
                    })
            rec.is_paid = is_paid

    def generate_report(self):
        self.ensure_one()
        self.env['project.contractors.line'].search([('contractors_id', '=', self.id)]).unlink()
        domain = [
            ('date', '>=', self.start_date),
            ('date', '<=', self.end_date),
            ('is_paid', '=', False),
            ('employee_type', '=', self.employee_type),
        ]
        contractors_lines = []
        data_dict = {}
        analytic_lines = self.env['account.analytic.line'].search(domain).mapped(
            lambda line: data_dict.update(
                {line.employee_id.id: data_dict.get(line.employee_id.id, self.env['account.analytic.line']) + line}
            )
        )
        for key in data_dict.keys():
            lines_data = {}
            for line in data_dict[key]:
                hours_spent = line.unit_amount
                contract_pay_rate = line.employee_id.contract_pay_rate
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
                if data not in lines_data:
                    lines_data[data] = {
                        'employee_id': key,
                        'description': data,
                        'hours_spent': hours_spent,
                        'contract_pay_rate': contract_pay_rate,
                        'bamboo_currency_id': line.employee_id.bamboo_currency_id.id,
                        'amount': contract_pay_rate * hours_spent,
                        'contractors_id': self.id,
                    }
                else:
                    lines_data[data]['hours_spent'] += hours_spent
                    lines_data[data]['amount'] += contract_pay_rate * hours_spent

            for c_line in lines_data.values():
                contractors_lines.append((0, 0, c_line))

        self.write({
            'contractors_line_ids': contractors_lines,
            'analytic_line_ids': reduce(lambda x, y: x + y, data_dict.values()),
            'is_generate': True,
        })

    def generate_invoice(self):
        account_move_ids = []
        for contractor in self:
            vendor_bills = {}
            for line in contractor.contractors_line_ids:
                employee = line.employee_id
                account_asset_counterpart_id = line.employee_id.account_asset_counterpart_id
                if not employee.related_contact_id:
                    partner = self.env['res.partner'].create({
                        'name': employee.name,
                        'email': employee.work_email,
                    })
                    employee.write({
                        'related_contact_id': partner.id,
                    })
                if employee not in vendor_bills:
                    vendor_bills[employee] = {
                        'partner_id': employee.related_contact_id.id,
                        'move_type': 'in_invoice',
                        'invoice_line_ids': [],
                        'currency_id': employee.bamboo_currency_id.id,
                    }
                vendor_bill = vendor_bills[employee]
                if contractor.product_id:
                    vendor_bill['invoice_line_ids'].append((0, 0, {
                        'product_id': contractor.product_id.id,
                        'name': line.description,
                        'quantity': line.hours_spent,
                        'price_unit': line.contract_pay_rate,
                        'currency_id': employee.bamboo_currency_id.id,
                    }))
                else:
                    vendor_bill['invoice_line_ids'].append((0, 0, {
                        'account_id': account_asset_counterpart_id,
                        'name': line.description,
                        'quantity': line.hours_spent,
                        'price_unit': line.contract_pay_rate,
                        'currency_id': employee.bamboo_currency_id.id,
                    }))
            vendor_bills_list = list(vendor_bills.values())
            vendor_bills_objs = self.env['account.move'].create(vendor_bills_list)
            account_move_ids += vendor_bills_objs.ids

        self.line_is_paid()
        self.write({
            'account_move_ids': account_move_ids,
            'state': 'in_progress',
        })

    def line_is_paid(self):
        for contractors in self:
            contractors.analytic_line_ids.write({'is_paid': True})

    def open_analytic_lines(self):
        action = self.env.ref('analytic.account_analytic_line_action').read()[0]
        action['domain'] = [('id', 'in', self.analytic_line_ids.ids)]
        action['context'] = {'group_by': ['employee_id', 'project_id', 'product_version_id', 'work_type_id', 'epic_id']}
        return action

    def open_vendor_bills(self):
        action = self.env.ref('account.action_move_in_invoice_type').read()[0]
        action['domain'] = [('id', 'in', self.account_move_ids.ids)]
        action['context'] = {'group_by': ['partner_id']}
        return action

    def unlink(self):
        for line in self:
            if line.state in ['in_progress', 'done']:
                raise UserError(_('You cannot delete a locked Project Invoice B2B Contactors.'))
        return super(ProjectContractors, self).unlink()

    def write(self, vals):
        for line in self:
            if line.state in ['in_progress', 'done']:
                raise UserError(_('You cannot edit a locked Project Invoice B2B Contactors.'))
        return super(ProjectContractors, self).write(vals)

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('project.contractors.sequence') or _('New')
        result = super(ProjectContractors, self).create(vals)
        return result
