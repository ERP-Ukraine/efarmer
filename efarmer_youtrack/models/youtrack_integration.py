import requests

from odoo import fields, models, api

PROJECT_KEY = 'shortName'

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

    project_code = fields.Char()

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
    
    def _filter_project_response(self, response):
        res = [obj for obj in response if obj[PROJECT_KEY] == self.project_code]
        return res

    def _find_odoo_project(self, project_code):
        project_obj = self.env['project.project']
        project = project_obj.search([('project_code', '=', project_code)], limit=1)
        return project and True or False

    def _create_project(self, vals):
        project_obj = self.env['project.project']
        project_obj.create({
            'name': vals.get(PROJECT_KEY),
            'project_code': vals.get(PROJECT_KEY),
            'youtrack_id': vals.get('id'),
        })
        return True

    def get_all_projects(self):
        get_all_projects_url = 'admin/projects?fields=name,shortName&archived=True'
        projects = self._send_youtrack_request(get_all_projects_url) or []
        print(projects)
        print(len(projects))

    def youtrackIntegrationApiGetProjectByCode(self):
        if self.project_code:
            # get_project_url = 'issues?fields=id,summary,project(name)&query=summary:{FieldBee Toolbox Firmware and Base static}'
            # get_project_url = 'admin/projects/78-29?fields=name,shortName,id,leader,description'
            get_project_url = 'admin/projects?fields=name,shortName,id&query={}'.format(self.project_code)
            response = self._send_youtrack_request(get_project_url) or []
            if response:
                if len(response) > 1:
                    project_dict = self._filter_project_response(response)
            project_dict = response[0]

            if not self._find_odoo_project(project_dict.get(PROJECT_KEY)):
                self._create_project(project_dict)
        
            self.project_code = None
