# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).


import requests
from datetime import datetime, timedelta, date

from odoo import fields, models, _
from odoo.exceptions import ValidationError


PROJECT_KEY = 'shortName'
CUSTOM_FIELDS_MAP = {
    'Estimation': 'planned_hours',
    'Type': 'issue_type_id',
    'Product version': 'product_version_id',
    'Name PL': 'name_pl',
    'Product': 'product_id',
    }


class YoutrackIntegration(models.Model):
    _name = 'youtrack.integration'
    _description = 'YouTrack Integration'

    def _get_api_method(self):
        api_methods = [
            method for method in dir(self)
            if method.startswith('youtrackIntegrationApi') and callable(getattr(self, method))
        ]
        return [(x, x.replace('youtrackIntegrationApi', '')) for x in api_methods]

    api_method = fields.Selection(_get_api_method, string='API Method')

    name = fields.Char(
        string='Name',
    )

    api_key = fields.Char(
        string='Token',
    )

    api_key_attr = fields.Char(
        string='Token Attribute',
    )

    is_active = fields.Boolean(
        string='Active',
    )

    endpoint = fields.Char(
        string='Endpoint',
        required=True,
    )

    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )

    project_code = fields.Char()

    date_from = fields.Date(
        string='Start Date',
    )

    def run_operation(self):
        method_name = self.api_method
        api_method = getattr(self, method_name, None)
        if api_method:
            api_method()
        return True

    def _get_api_parameters(self, integration_id):
        integration = self.env['youtrack.integration'].browse(integration_id)
        if not integration or not integration.is_active:
            raise ValidationError(_('No active YouTrack Integration found!'))
        return integration.endpoint, integration.api_key_attr, integration.api_key

    def _send_youtrack_request(self, uri, integration_id=None):
        """
        Send request with Permanent API key
        """
        if integration_id:
            endpoint, api_key_attr, api_key = self._get_api_parameters(integration_id)
        else:
            endpoint, api_key_attr, api_key = self.endpoint, self.api_key_attr, self.api_key

        headers = {
            'Authorization': '{} {}'.format(api_key_attr, api_key),
            'Accept': 'application/json',
        }

        if endpoint.endswith('/'):
            endpoint = endpoint[:-1]

        request_url = '{}/{}'.format(endpoint, uri)
        resp = requests.get(request_url, headers=headers)

        if resp.status_code != 200:
            resp.raise_for_status()

        json_response = resp.json()

        return json_response

    def _filter_project_response(self, ext_projects):
        res = [project for project in ext_projects if project[PROJECT_KEY] == self.project_code]
        return res

    def _get_project_by_code(self, project_code):
        project = self.env['project.project'].search([
            ('project_code', '=', project_code)
        ], limit=1)
        return project or False

    def _get_obj_by_ext_id(self, model, value, operator='=', limit=1):
        obj = self.env[model].search([('youtrack_id', operator, value)], limit=limit)
        return obj

    def _get_obj_by_name(self, model, value, operator='=', limit=1):
        obj = self.env[model].search([('name', operator, value)], limit=limit)
        return obj

    def _get_ts_to_create(self, ext_ts):
        exist_ts = self._get_obj_by_ext_id('account.analytic.line', False, operator='!=', limit=None)
        exist_ts_ext_ids = exist_ts.mapped('youtrack_id')
        exist_projects = self._get_obj_by_ext_id('project.project', False, operator='!=', limit=None)
        exist_project_ext_ids = exist_projects.mapped('youtrack_id')

        ts_to_create = [ts for ts in ext_ts if ts['id'] not in exist_ts_ext_ids
                        and ts['issue']['project']['id'] in exist_project_ext_ids]
        return ts_to_create

    def _get_issue_type(self, ext_issue_type):
        issue_type = self._get_obj_by_name('youtrack.issue.type', ext_issue_type['name'])
        if not issue_type:
            issue_type = self.env['youtrack.issue.type'].create({
                'name': ext_issue_type['name'] or '',
                'youtrack_id': ext_issue_type['id'],
            })
        return issue_type.id

    def _get_product_version(self, ext_product_version):
        product_version = self._get_obj_by_name(
            'youtrack.product.version',
            ext_product_version['name'],
        )
        if not product_version:
            product_version = self.env['youtrack.product.version'].create({
                'name': ext_product_version['name'] or '',
                'youtrack_id': ext_product_version['id'],
            })
        return product_version.id

    def _get_product(self, ext_product):
        product = self._get_obj_by_name('account.asset', ext_product['name'])
        if not product:
            product = self.env['account.asset'].create({
                'name': ext_product['name'] or '',
                'youtrack_id': ext_product['id'],
            })
        return product.id

    def _get_work_type(self, vals):
        if not vals.get('type', False):
            return None
        work_type = self._get_obj_by_ext_id('youtrack.work.type', vals['type']['id'])
        if not work_type:
            work_type = self.env['youtrack.work.type'].create({
                'youtrack_id': vals['type']['id'],
                'name': vals['type']['name'] or '',
            })

        return work_type.id

    def _minutes_to_hours(self, minutes):
        hours = float(minutes // 60 + minutes % 60 / 60)
        return hours

    def _get_api_customs_values(self, vals):
        custom_values = {}
        for field in vals['customFields']:
            if field.get('name') in CUSTOM_FIELDS_MAP:
                value = field['value']
                custom_values[CUSTOM_FIELDS_MAP.get(field['name'])] = value if value else None

        if custom_values.get('issue_type_id', False):
            ext_issue_type = custom_values['issue_type_id']
            custom_values['issue_type_id'] = self._get_issue_type(ext_issue_type)

        if custom_values.get('product_version_id', False):
            ext_product_version = custom_values['product_version_id']
            custom_values['product_version_id'] = self._get_product_version(ext_product_version)

        if custom_values.get('product_id', False):
            ext_product = custom_values['product_id']
            custom_values['product_id'] = self._get_product(ext_product)

        if custom_values.get('planned_hours', False):
            estimation_minutes = int(custom_values['planned_hours']['minutes'])
            planned_hours = self._minutes_to_hours(estimation_minutes)
            custom_values['planned_hours'] = planned_hours

        return custom_values

    def _get_employees_data(self, ext_employees):
        employees = self.env['hr.employee'].search([])
        emails = {employee.work_email: employee for employee in employees if employee.work_email}
        exist_employees_ext_ids = employees.mapped('youtrack_id')
        to_do_employees = [employee for employee in ext_employees if employee['id'] not in exist_employees_ext_ids]
        return emails, to_do_employees

    def _timestamp_to_date(self, timestamp):
        if len(str(timestamp)) == 13:
            res = date.fromtimestamp(timestamp / 1000)
        elif len(str(timestamp)) == 15:
            res = date.fromtimestamp(timestamp / 100000)

        return res

    def _create_project(self, vals):
        self.env['project.project'].create({
            'name': vals.get('name', ''),
            'project_code': vals.get(PROJECT_KEY, ''),
            'youtrack_id': vals.get('id', ''),
        })
        return True

    def _create_task(self, vals):
        project = self._get_obj_by_ext_id('project.project', vals['project']['id'])
        custom_values = self._get_api_customs_values(vals)

        new_vals = {
            'name': vals.get('summary') or '',
            'project_id': project.id or None,
            'youtrack_id': vals.get('id') or '',
            'task_code': vals.get('idReadable') or '',
            'planned_hours': custom_values.get('planned_hours'),
            'product_version_id': custom_values.get('product_version_id'),
            'issue_type_id': custom_values.get('issue_type_id'),
            'name_pl': custom_values.get('name_pl'),
        }
        if custom_values.get('product_id'):
            new_vals.update({
                'is_epic': True,
                'product_id': custom_values.get('product_id'),
            })
        new_task = self.env['project.task'].create(new_vals)
        return new_task

    def _create_ts(self, vals, employee):
        task = self._get_obj_by_ext_id('project.task', vals['issue']['id'])
        work_type_id = self._get_work_type(vals)
        date = self._timestamp_to_date(vals.get('date'))

        self.env['account.analytic.line'].create({
            'youtrack_id': vals.get('id'),
            'name': vals.get('text', ''),
            'date': date,
            'unit_amount': self._minutes_to_hours(vals['duration']['minutes']),
            'employee_id': employee.id,
            'work_type_id': work_type_id,
            'project_id': task.project_id.id if task.project_id else None,
            'task_id': task.id if task else None,
        })
        return True

    def _create_employee(self, vals):
        self.env['hr.employee'].create({
            'name': vals.get('fullName', ''),
            'work_email': vals.get('email', ''),
            'youtrack_id': vals.get('id', ''),
        })
        return True

    def _create_epic_links(self):
        epic_tasks = self.env['project.task'].search([
            ('is_epic', '=', True)
        ])
        for epic in epic_tasks:
            childs = self.env['project.task'].search([
                ('id', 'child_of', epic.child_ids.ids)
            ])
            for child in childs:
                child.epic_id = epic.id
                child.product_version_id = epic.product_version_id.id \
                    if epic.product_version_id else None

    def _validate_project_request(self):
        if self.project_code:
            if self._get_project_by_code(self.project_code):
                raise ValidationError(_(
                    'Project with code "{}" already exists in Odoo.'
                    ).format(self.project_code))
        else:
            raise ValidationError(_(
                    'You need to set Project Code for importing Project.'
                    ))

    def _validate_work_items_request(self):
        if not self.date_from:
            raise ValidationError(_('You need to set Start Date  '
                                    'for importing Work Items.'))

    def api_get_project(self, project_code):
        get_project_url = 'admin/projects?fields=name,shortName,'\
                          'id&$top=1000000&query={}'.format(project_code)
        ext_project = self._send_youtrack_request(get_project_url) or []
        if ext_project:
            # we can't receive exact response with such request,
            # and we need to avoid creation of more than one projects
            if len(ext_project) > 1:
                ext_project = self._filter_project_response(ext_project)
            self._create_project(ext_project[0])

    def api_get_employees(self):
        get_employee_url = "users?fields=id,fullName,email&$top=100000"
        ext_employees = self._send_youtrack_request(get_employee_url) or []
        if ext_employees:
            # write youtrack_id if employee with imported email exists in Odoo,
            # otherwise create employee
            emails, to_do_employees = self._get_employees_data(ext_employees)
            for employee in to_do_employees:
                ext_email = employee.get('email', False)
                if ext_email in emails:
                    odoo_employee = emails[ext_email]
                    odoo_employee.youtrack_id = employee.get('id', None)
                else:
                    self._create_employee(employee)

    def api_get_task(self, task_ext_id, integration_id, child=None):
        task = self._get_obj_by_ext_id('project.task', task_ext_id)
        if task:
            if child:
                child.parent_id = task.id
            return task

        get_tasks_url = 'issues/{}?fields=id,idReadable,summary,project(id),'\
                        'parent(issues(id,project(id))),customFields(name,'\
                        'value(id,name,minutes))&customFields=type&'\
                        'customFields=Estimation&customFields=Product version&'\
                        'customFields=Product&customFields=Name PL&$top=1'.format(task_ext_id)
        ext_task = self._send_youtrack_request(get_tasks_url, integration_id=integration_id) or []
        if ext_task:
            task = self._create_task(ext_task)
            if child:
                child.parent_id = task.id

            parent_task = ext_task['parent']['issues']
            # get and create parent task recursively
            if parent_task:
                parent_id = parent_task[0]['id']
                parent_project_id = parent_task[0]['project']['id']
                parent_project = self._get_obj_by_ext_id('project.project', parent_project_id)
                if parent_project:
                    self.api_get_task(parent_id, integration_id, child=task)
            return task

    def api_get_work_items(self, start, integration_id):
        # import work items (timesheets) for all existing employees with yourack_id
        employees = self._get_obj_by_ext_id('hr.employee', False, operator='!=', limit=None)
        for employee in employees:
            get_ts_url = 'workItems?fields=date,duration(minutes),author(id),text,'\
                         'type,id,type(id,name),issue(id,project(id))&startDate={}'\
                         '&author={}&$top=100000'.format(start, employee.youtrack_id)
            ext_ts = self._send_youtrack_request(get_ts_url, integration_id=integration_id) or []
            if ext_ts:
                # filter out existing ts and ts with project, that doesn't exist in Odoo
                ts_to_create = self._get_ts_to_create(ext_ts)
                for ts in ts_to_create:
                    # TODO: run api_get_task with_delay() ??
                    self.api_get_task(ts['issue']['id'], integration_id)
                    self._create_ts(ts, employee)
        # create links for all childs to its epic task
        self._create_epic_links()

    def youtrackIntegrationApiGetProject(self):
        self._validate_project_request()
        self.with_delay().api_get_project(self.project_code)

    def youtrackIntegrationApiGetWorkItems(self, integration_id=None, period=None):
        if self.env.context.get('with_cron', False):
            start = (datetime.today() - timedelta(days=period)).strftime('%Y-%m-%d')
        else:
            self._validate_work_items_request()
            start = self.date_from.strftime('%Y-%m-%d')

        self.with_delay().api_get_work_items(start, integration_id)

    def youtrackIntegrationApiGetEmployees(self):
        self.with_delay().api_get_employees()
