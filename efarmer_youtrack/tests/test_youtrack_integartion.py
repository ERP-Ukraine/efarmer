# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).


import requests
from datetime import datetime, date
from unittest.mock import patch

from odoo.exceptions import ValidationError

from .common import TestYoutrackIntegrationCommon, API_PROJECT_RESPONSE, \
    API_EMPLOYEE_RESPONSE, API_WORK_ITEM_RESPONSE, API_TASK_RESPONSE, \
        API_PARENT_TASK_RESPONSE


class TestYoutrackIntegration(TestYoutrackIntegrationCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(
            cls.env.context,
            test_queue_job_no_delay=True,
        ))

    def setUp(self):
        super(TestYoutrackIntegration, self).setUp()

        self.company = self.env['res.company'].create({'name': 'Test Company'})

        self.yt_integration = self.env['youtrack.integration'].create({
            'name': 'Test Integration',
            'api_key': 'test_api_key',
            'api_key_attr': 'test_api_key_attr',
            'is_active': True,
            'endpoint': 'https://fieldbee.youtrack.cloud.test/api',
            'company_id': self.company.id,
        })

    def _create_project(self):
        project = self.env['project.project'].create(
            {
                'name': 'Test Project',
                'youtrack_id': '1-1',
                'company_id': self.company.id,
            }
        )
        return project

    def _create_task(self, project):
        task = self.env['project.task'].create(
            {
                'name': 'Test Task',
                'youtrack_id': '99-99',
                'project_id': project.id,
                'company_id': self.company.id,
            }
        )
        return task

    def _create_employee(self, youtrack_id=None):
        self.env['hr.employee'].create(
            {
                'name': 'Test User 1',
                'youtrack_id': youtrack_id if youtrack_id else '',
                'work_email': 'test@user_1.com',
                'company_id': self.company.id,
            }
        )

    def test_send_youtrack_request(self):
        """
        Testing the logic of the _send_youtrack_request method.
        """
        get_result = requests.Response()
        get_result.__dict__.update({
            '_content': b'[{"shortName":"DEMO","name":"Demo","id":"78-29","$type":"Project"}]',
            '_content_consumed': True,
            'status_code': 200,
            'encoding': 'utf-8',
            'reason': 'OK',
        })

        with self.cr.savepoint(), patch.object(requests, 'get', return_value=get_result):
            json_response = self.yt_integration._send_youtrack_request('url')
            self.assertTrue(json_response)

        get_result.__dict__.update({
            '_content': False,
            '_content_consumed': False,
            'status_code': 404,
            'encoding': None,
            'reason': False,
        })
        with self.cr.savepoint(), patch.object(requests, 'get', return_value=get_result, ) \
                as mock_requests_get:
            mock_requests_get.side_effect = requests.exceptions.ConnectionError('ConnectionError')

            with self.assertRaises(requests.exceptions.ConnectionError):
                json_response = self.yt_integration._send_youtrack_request('url')
                self.assertIsNone(json_response)
            mock_requests_get.assert_called_once()

    def test_api_job_created(self):
        """
        Testing the logic of running api methods using jobs.
        """
        request_project_code = 'TEST'
        self.yt_integration.write(
            {
                'api_method': 'youtrackIntegrationApiGetProject',
                'project_code': request_project_code,
            }
        )
        # enable jobs
        self.yt_integration.with_context(test_queue_job_no_delay=False).run_operation()

        pattern_job_func_string = 'youtrack.integration({},).api_get_project(\'{}\')'.format(
            self.yt_integration.id, request_project_code)
        integration_job = self.env['queue.job'].search([
            ('func_string', 'ilike', pattern_job_func_string),
        ])

        self.assertTrue(integration_job)

    def test_api_get_project(self):
        """
        Testing functionality of importing project.
        """
        project_code = 'TEST'

        msg = 'You need to set Project Code for importing Project.'
        with self.assertRaises(ValidationError, msg=msg):
            self.yt_integration.youtrackIntegrationApiGetProject()

        mock_request = self._create_patch_object(type(self.yt_integration), '_send_youtrack_request')
        mock_request.return_value = API_PROJECT_RESPONSE

        self.yt_integration.project_code = project_code
        self.yt_integration.youtrackIntegrationApiGetProject()

        # check that project was created with wright attributes
        project = self.env['project.project'].search([('project_code', '=', project_code)])
        self.assertEqual(project.name, API_PROJECT_RESPONSE[0].get('name', ''))
        self.assertEqual(project.youtrack_id, API_PROJECT_RESPONSE[0].get('id', ''))

        msg = 'Project with code "{}" already exists in Odoo.'.format(project_code)
        with self.assertRaises(ValidationError, msg=msg):
            self.yt_integration.youtrackIntegrationApiGetProject()

        mock_request.assert_called_once()

    def test_api_get_employees(self):
        """
        Testing functionality of importing employees.
        Response data include:
        - employee that exists in system without youtrack_id (expect.: write youtrack_id)
        - employee that doesn't exist in system (expect.: create)
        - employee with no email defined (expect.: pass)
        """
        self._create_employee()

        mock_request = self._create_patch_object(type(self.yt_integration), '_send_youtrack_request')
        mock_create_employee = self._create_patch_object(type(self.env['hr.employee']), 'create')
        mock_write_employee = self._create_patch_object(type(self.env['hr.employee']), 'write')
        mock_request.return_value = API_EMPLOYEE_RESPONSE

        self.yt_integration.youtrackIntegrationApiGetEmployees()

        expected_create_vals = {
            'name': API_EMPLOYEE_RESPONSE[1].get('fullName', ''),
            'work_email': API_EMPLOYEE_RESPONSE[1].get('email', ''),
            'youtrack_id': API_EMPLOYEE_RESPONSE[1].get('id', ''),
            'company_id': self.company.id,
        }
        expected_update_vals = {
            'youtrack_id': API_EMPLOYEE_RESPONSE[0].get('id', ''),
        }

        # check that only one entry was created
        mock_create_employee.assert_called_once_with(expected_create_vals)
        # check that only one entry was updated
        mock_write_employee.assert_called_once_with(expected_update_vals)

    def test_api_get_work_items(self):
        """
        Testing functionality of importing work items (timesheets)
        separately, without the process of geting and creating tasks.
        """
        ts_obj = self.env['account.analytic.line']
        self._create_employee(youtrack_id='11-11')
        self.env['youtrack.work.type'].create({'name': 'Test Work Type'})

        msg = 'You need to set Start Date for importing Work Items.'
        with self.assertRaises(ValidationError, msg=msg):
            self.yt_integration.youtrackIntegrationApiGetWorkItems()

        self.yt_integration.date_from = datetime.today().strftime('%Y-%m-%d')

        mock_request = self._create_patch_object(type(self.yt_integration), '_send_youtrack_request')
        mock_request.return_value = API_WORK_ITEM_RESPONSE
        # mocking geting of task to avoid process of its creation
        self._create_patch_object(type(self.yt_integration), 'api_get_task')

        project_youtrack_id = API_WORK_ITEM_RESPONSE[0].get('id', '')

        # try to get and create timesheet when project doesn't exist
        self.yt_integration.youtrackIntegrationApiGetWorkItems()
        created = ts_obj.search([('youtrack_id', '=', project_youtrack_id)])
        self.assertFalse(created)

        # creating project and simulating process of importing task
        project = self._create_project()
        task = self._create_task(project)

        mock_create_work_type = self._create_patch_object(type(self.env['youtrack.work.type']), 'create')
        self.yt_integration.youtrackIntegrationApiGetWorkItems()
        created = ts_obj.search([('youtrack_id', '=', project_youtrack_id)])

        # expect that timesheet was created
        self.assertTrue(created, 'Timesheet must be created!')
        self.assertEqual(created.task_id, task)
        self.assertEqual(created.project_id, project)
        self.assertEqual(created.date, date.fromtimestamp(1670198400000 / 1000))
        self.assertEqual(created.unit_amount, 62 // 60 + 62 % 60 / 60)

        # expect that work type with the same name already exists, no need to create it
        mock_create_work_type.assert_not_called()

        # expect that timesheet with the same youtrack_id already exists, no need to create it
        mock_create_ts = self._create_patch_object(type(ts_obj), 'create')
        self.yt_integration.youtrackIntegrationApiGetWorkItems()
        mock_create_ts.assert_not_called()

    def test_api_get_task(self):
        """
        Testing functionality of importing tasks.
        Making request for task, and if t has parent making
        requests until parent will not be found.
        """
        self._create_project()

        mock_request = self._create_patch_object(type(self.yt_integration), '_send_youtrack_request')
        # define several return values through side_effect to simulate
        # recursive request of tasks
        mock_request.side_effect = [API_TASK_RESPONSE, API_PARENT_TASK_RESPONSE]

        child_task_ext_id = API_TASK_RESPONSE.get('id')
        parent_task_ext_id = API_PARENT_TASK_RESPONSE.get('id')

        self.yt_integration.api_get_task(child_task_ext_id)

        # check whether tasks were created
        child_task = self.env['project.task'].search([('youtrack_id', '=', child_task_ext_id)])
        parent_task = self.env['project.task'].search([('youtrack_id', '=', parent_task_ext_id)])

        self.assertTrue(parent_task)
        # check field values
        self.assertTrue(all([parent_task.is_epic, parent_task.product_id, parent_task.task_code,
            parent_task.product_version_id, parent_task.issue_type_id, parent_task.name_pl]))
        self.assertEqual(parent_task.planned_hours, 550 // 60 + 550 % 60 / 60)

        self.assertTrue(child_task)
        # check whether link between tasks was created
        self.assertEqual(child_task.parent_id, parent_task)

        self.yt_integration._create_epic_links()

        # check whether epic task and product version of parent (epic)
        # task were filled on child task
        self.assertEqual(child_task.epic_id, parent_task)
        self.assertEqual(child_task.product_version_id, parent_task.product_version_id)

        mock_create_task = self._create_patch_object(type(self.env['project.task']), 'create')
        self.yt_integration.api_get_task(child_task_ext_id)

        # check that after re-import tasks with same youtrack_id weren't created
        mock_create_task.assert_not_called()

    def test_external_object_unique(self):
        """
        Сheck the uniqueness of existing objects
        """
        model, field, value = 'youtrack.issue.type', 'name', 'Test Type'
        issue_type = self.env[model].create({field: value})
        issue_type.copy()

        msg = 'There are more than one objects of model {} with the same {}!!'.format(
            model, field)
        with self.assertRaises(ValidationError, msg=msg):
            self.yt_integration._get_object(model, [(field, '=', value)], check_unique=True)

    def test_get_object_by_name(self):
        """
        Get object by name and create if not found
        """
        custom_data = API_WORK_ITEM_RESPONSE[0].get('type')
        model = 'youtrack.work.type'
        mock_create_work_type = self._create_patch_object(type(self.env[model]), 'create')

        self.yt_integration._get_object_by_name(model, custom_data)

        expected_create_vals = {
            'name': custom_data['name'],
            'youtrack_id': custom_data['id']
        }
        mock_create_work_type.assert_called_once_with(expected_create_vals)

    def test_filter_project_response(self):
        """
        Testing of project response filtering if integration return
        more than one object with similar name
        """
        self.yt_integration.project_code = 'TEST'
        response = [{'shortName': 'TEST'}, {'shortName': 'TEST1'}]

        res = self.yt_integration._filter_project_response(response)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]['shortName'], self.yt_integration.project_code)
