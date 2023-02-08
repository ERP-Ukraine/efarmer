# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).


import requests
from datetime import datetime, timedelta, date

from odoo import fields, models, _
from odoo.exceptions import ValidationError


PROJECT_KEY = 'shortName'


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

    def _get_object(self, model, field, value, operator='=', limit=None, check_unique=False):
        obj = self.env[model].search([(field, operator, value)], limit=limit)
        if check_unique:
            self._check_unique(obj, field)
        return obj

    def _check_unique(self, object, field):
        if len(object) > 1:
            raise ValidationError(_(
                'There are more than one objects of model {} with the same {}!!'
            ).format(object[0]._name, field))
        return True

    def _create_object(self, model, vals):
        obj = self.env[model].create(vals)
        return obj

    def _get_ts_to_create(self, ext_ts):
        exist_ts = self._get_object('account.analytic.line', 'youtrack_id', False, operator='!=')
        exist_ts_ext_ids = exist_ts.mapped('youtrack_id')
        exist_projects = self._get_object('project.project', 'youtrack_id', False, operator='!=')
        exist_project_ext_ids = exist_projects.mapped('youtrack_id')

        ts_to_create = [ts for ts in ext_ts if ts['id'] not in exist_ts_ext_ids
                        and ts['issue']['project']['id'] in exist_project_ext_ids]
        return ts_to_create

    def _get_object_by_name(self, model, custom_data):
        obj = self._get_object(model, 'name', custom_data['name'], check_unique=True)
        if not obj:
            vals = {
                'name': custom_data['name'] or '',
                'youtrack_id': custom_data['id'],
            }
            obj = self._create_object(model, vals)
        return obj

    def _minutes_to_hours(self, minutes):
        hours = float(minutes // 60 + minutes % 60 / 60)
        return hours

    def _get_api_customs_values(self, vals):
        CUSTOM_FIELDS_MAP = {
            'Estimation': ('planned_hours', None),
            'Type': ('issue_type_id', 'youtrack.issue.type'),
            'Product version': ('product_version_id', 'youtrack.product.version'),
            'Name PL': ('name_pl', None),
            'Product': ('product_id', 'account.asset'),
        }

        custom_values = {}
        for field in vals['customFields']:
            field_name = field.get('name')
            if field_name in CUSTOM_FIELDS_MAP:
                custom_data = field['value']
                odoo_field, model = CUSTOM_FIELDS_MAP.get(field_name)
                if not model:
                    custom_values[odoo_field] = custom_data
                else:
                    custom_values[odoo_field] = self._get_object_by_name(model, custom_data).id \
                        if custom_data else None

        if custom_values.get('planned_hours', False):
            planned_hours = self._minutes_to_hours(custom_values['planned_hours']['minutes'])
            custom_values['planned_hours'] = planned_hours

        return custom_values

    def _get_employees_data(self, ext_empls):
        update_data = {}
        # find employees in Odoo with emails from YouTrack
        ext_emails = [employee['email'] for employee in ext_empls]
        empls = self.env['hr.employee'].search([('work_email', 'in', ext_emails)])
        empls_emails = empls.mapped('work_email')
        # define create list of YouTrack employees which have
        # email and don't exist in Odoo
        empls_to_create = [empl for empl in ext_empls
                           if empl['email'] and empl['email'] not in empls_emails]

        # check if there are employees in Odoo without youtrack_id
        # and prepare data for updating them
        empls_no_ext_ids = empls.filtered(lambda x: not x.youtrack_id)
        if empls_no_ext_ids:
            empls_no_ext_ids = {empl.work_email: empl for empl in empls_no_ext_ids}
            update_data = {empl['id']: empls_no_ext_ids.get(empl['email']) for empl in ext_empls
                           if empl['email'] in empls_no_ext_ids}
        return empls_to_create, update_data

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
        project = self._get_object(
            'project.project',
            'youtrack_id',
            vals['project']['id'],
            check_unique=True,
        )
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
        task = self._get_object(
            'project.task',
            'youtrack_id',
            vals['issue']['id'],
            check_unique=True,
        )
        work_type_id = self._get_object_by_name('youtrack.work.type', vals['type']).id \
            if vals.get('type') else None
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
            if self._get_object('project.project', 'project_code', self.project_code, limit=1):
                raise ValidationError(_(
                    'Project with code "{}" already exists in Odoo.'
                ).format(self.project_code))
        else:
            raise ValidationError(_(
                'You need to set Project Code for importing Project.'
            ))

    def _validate_work_items_request(self):
        if not self.date_from:
            raise ValidationError(_(
                'You need to set Start Date for importing Work Items.'
            ))

    def api_get_project(self, project_code):
        get_project_url = 'admin/projects?fields=name,shortName,'\
                          'id&$top=100000&query={}'.format(project_code)
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
            # create employee if employee with imported email doesn't exists
            # in Odoo, otherwise write youtrack_id if it's empty
            empls_to_create, update_data = self._get_employees_data(ext_employees)

            if empls_to_create:
                for employee in empls_to_create:
                    self._create_employee(employee)

            if update_data:
                for youtrack_id, employee in update_data.items():
                    employee.youtrack_id = youtrack_id

    def api_get_task(self, task_ext_id, integration_id, child=None):
        """
        Check if task exists in Odoo, otherwise get it from
        integration and repeat this operation recursively
        as long as the task has a parent.
        After each recursive execution create link between parent
        and child tasks.
        """
        task = self._get_object('project.task', 'youtrack_id', task_ext_id, check_unique=True)
        if task:
            if child:
                child.parent_id = task.id
            return True

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
                parent_project = self._get_object(
                    'project.project',
                    'youtrack_id',
                    parent_project_id,
                    check_unique=True,
                )
                # create task if project exists in Odoo
                if parent_project:
                    self.api_get_task(parent_id, integration_id, child=task)
            return True

    def api_get_work_items(self, start, integration_id):
        # import work items (timesheets) for all existing employees with yourack_id
        employees = self._get_object('hr.employee', 'youtrack_id', False, operator='!=')
        for employee in employees:
            get_ts_url = 'workItems?fields=date,duration(minutes),author(id),text,'\
                         'type,id,type(id,name),issue(id,project(id))&startDate={}'\
                         '&author={}&$top=100000'.format(start, employee.youtrack_id)
            ext_ts = self._send_youtrack_request(get_ts_url, integration_id=integration_id) or []
            if ext_ts:
                # filter out existing ts and ts with project, that doesn't exist in Odoo
                ts_to_create = self._get_ts_to_create(ext_ts)
                for ts in ts_to_create:
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
