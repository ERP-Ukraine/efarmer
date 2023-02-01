import requests
from datetime import date, timedelta

from odoo import fields, models, api, _
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
    _name = 'youtrack.inegration'
    _description = 'YouTrack Integration'
    

    @api.model
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

    def _send_youtrack_request(self, uri):
        """
        Send request with Permanent API key
        """
        headers = {
            'Authorization': '{} {}'.format(self.api_key_attr, self.api_key),
            'Accept': 'application/json',
            'Cache-Control': 'no-cache',
        }
        if self.endpoint.endswith('/'):
            self.endpoint = self.endpoint[:-1]

        try:
            request_url = '{}/{}'.format(self.endpoint, uri)
            resp = requests.get(request_url, headers=headers)

            if resp.status_code != 200:
                resp.raise_for_status()

            json_response = resp.json()

            return json_response

        except requests.exceptions.ConnectionError as e:
            pass
        except requests.exceptions.RequestException as e:
            pass

        return None
    
    def _filter_project_response(self, ext_projects):
        res = [project for project in ext_projects if project[PROJECT_KEY] == self.project_code]
        return res

    def _get_odoo_project(self, project_code):
        project = self.env['project.project'].search([('project_code', '=', project_code)], limit=1)
        return project or False

    def _get_task_external_ids(self):
        ext_projects = self.env['project.task'].search([('youtrack_id', '!=', False)])
        task_ext_ids = ext_projects.mapped('youtrack_id')
        return task_ext_ids

    def _get_tasks_to_create(self, ext_tasks):
        exist_tasks = self.env['project.task'].search([('youtrack_id', '!=', False)])
        exist_task_ext_ids = exist_tasks.mapped('youtrack_id')
        tasks_to_create = [task for task in ext_tasks if task['id'] not in exist_task_ext_ids]
        return tasks_to_create
    
    def _get_odoo_issue_type(self, ext_issue_type):
        issue_type = self.env['youtrack.issue.type'].search([
            ('youtrack_id', '=', ext_issue_type['id'])
        ])
        if not issue_type:
            issue_type = self.env['youtrack.issue.type'].create({
                'name': ext_issue_type['name'] or '',
                'youtrack_id': ext_issue_type['id'],
            })
        return issue_type.id

    def _get_odoo_product_version(self, ext_product_version):
        product_version = self.env['youtrack.product.version'].search([
            ('youtrack_id', '=', ext_product_version['id'])
        ])
        if not product_version:
            product_version = self.env['youtrack.product.version'].create({
                'name': ext_product_version['name'] or '',
                'youtrack_id': ext_product_version['id'],
            })
        return product_version.id

    def _get_api_customs_values(self, vals):
        custom_values = {}
        for field in vals['customFields']:
            if field.get('name') in CUSTOM_FIELDS_MAP:
                value = field['value']
                custom_values[CUSTOM_FIELDS_MAP.get(field['name'])] = value if value else None

        if custom_values['issue_type_id']:
            ext_issue_type = custom_values['issue_type_id']
            custom_values['issue_type_id'] = self._get_odoo_issue_type(ext_issue_type)

        if custom_values['product_version_id']:
            ext_product_version = custom_values['product_version_id']
            custom_values['product_version_id'] = self._get_odoo_product_version(ext_product_version)

        if custom_values['planned_hours']:
            estimation_minutes = int(custom_values['planned_hours']['minutes'])
            planned_hours = float(estimation_minutes // 60 + estimation_minutes % 60 / 60)
            custom_values['planned_hours'] = planned_hours

        return custom_values

    def _get_employees_data(self, ext_employees):
        employees = self.env['hr.employee'].search([])
        emails = {employee.work_email:employee for employee in employees if employee.work_email}
        exist_employees_ext_ids = employees.mapped('youtrack_id')
        to_do_employees = [employee for employee in ext_employees if employee['id'] not in exist_employees_ext_ids]
        return emails, to_do_employees


    def _create_project(self, vals):
        project_obj = self.env['project.project']
        project_obj.create({
            'name': vals.get('name'),
            'project_code': vals.get(PROJECT_KEY),
            'youtrack_id': vals.get('id'),
        })
        return True

    def _create_task(self, vals):
        project = self.env['project.project'].search(
            [('youtrack_id', '=', vals['project']['id'])]
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
                # 'product_id': None
            })
        new_task = self.env['project.task'].create(new_vals)
        return new_task

    def _create_employee(self, vals):
        self.env['hr.employee'].create({
            'name': vals.get('fullName', ''),
            'work_email': vals.get('email', ''),
            'youtrack_id': vals.get('id', ''),
        })
        return True
    
    # def find_childs_recursively(self, parent):
    #         childs = parent.child_ids

    #         self.env['project.task'].search([('id', 'child_of', parent.child_ids.ids)])
    #         if len(childs) != 0:
    #             for child in childs:
    #                 self.find_childs_recursively(child)

    #         return childs

    def _create_links(self, child_links, created_tasks):
        if child_links and created_tasks:
            for child_task, parent_youtrack_id in child_links.items():
                child_task.parent_id = created_tasks.get(parent_youtrack_id).id
            
            epic_tasks = [task for task in created_tasks.values() if task.is_epic]
            
            for epic in epic_tasks:
                if epic.child_ids:
                    childs = self.env['project.task'].search([
                        ('id', 'child_of', epic.child_ids.ids)
                    ])
                    for child in childs:
                        child.epic_id = epic.id
                        child.product_version_id = epic.product_version_id.id \
                            if epic.product_version_id else None

    def youtrackIntegrationApiGetProject(self):
        if self.project_code:
            if self._get_odoo_project(self.project_code):
                raise ValidationError(_(
                    'Project with code "{}" exists in Odoo.'
                    ).format(self.project_code))

            get_project_url = 'admin/projects?fields=name,shortName,id&$top=1000000&query={}'.format(self.project_code)
            ext_project = self._send_youtrack_request(get_project_url) or []
            if ext_project:
                if len(ext_project) > 1:
                    ext_project = self._filter_project_response(ext_project)
                self._create_project(ext_project[0])
        
            self.project_code = None

    def youtrackIntegrationApiGetTasks(self):
        if self.project_code:
            project = self._get_odoo_project(self.project_code)
            if not project:
                raise ValidationError(_('Project with code "{}" does\'t exist in Odoo. '
                                        'You first need to import it or check '
                                        'entered value.').format(self.project_code))

            get_tasks_url = "admin/projects/{}/issues?fields=id,idReadable,summary,"\
                            "project(id),parent(issues(id,project(id))),"\
                            "customFields(name,value(id,name,minutes))&customFields=type&"\
                            "customFields=Estimation&customFields=Product version&"\
                            "customFields=Product&customFields=Name PL&$top=100000".format(project.youtrack_id)

            ext_tasks = self._send_youtrack_request(get_tasks_url) or []
            # print(ext_tasks)
            if ext_tasks:
                tasks_to_create = self._get_tasks_to_create(ext_tasks)
                created_tasks = {}
                child_links = {}
                for task_dict in tasks_to_create:
                    task = self._create_task(task_dict)
                    parent_task = task_dict['parent']['issues']
                    if parent_task:
                        parent_id = parent_task[0]['id']
                        parent_project_id = parent_task[0]['project']['id']
                        if parent_project_id == task_dict['project']['id']:
                            child_links[task] = parent_id
                    created_tasks[task.youtrack_id] = task

                # link tasks
                self._create_links(child_links, created_tasks)

            self.project_code = None

    def youtrackIntegrationApiGetWorItems(self, period=None):
        if not self.date_from:
            raise ValidationError(_('You need to set Start Date for importing Work Items.'))
        employees = self.env['hr.employee'].search([('youtrack_id', '!=', False)])
        start = self.date_from.strftime('%Y-%m-%d')
        print(start)
        exist_tasks = self.env['project.task'].search([('youtrack_id', '!=', False)])
        for employee in employees:

            get_work_items_url = "workItems?fields=date,created,duration(minutes),author(email),"\
                                "text,type,id,type,issue(id,project(id,shortName))&startDate={}"\
                                "&author={}&$top=10000".format(start, employee.youtrack_id)
            ext_work_items = self._send_youtrack_request(get_work_items_url) or []

            print(ext_work_items)

        self.date_from = None

    def youtrackIntegrationApiGetEmployees(self):
        get_employee_url = "users?fields=id,fullName,email&$top=100000"
        ext_employees = self._send_youtrack_request(get_employee_url) or []

        if ext_employees:
            emails, to_do_employees = self._get_employees_data(ext_employees) 
            for employee in to_do_employees:
                ext_email = employee.get('email', False)
                if ext_email in emails:
                    odoo_employee = emails[ext_email]
                    odoo_employee.youtrack_id = employee.get('id', None)
                else:
                    self._create_employee(employee)
