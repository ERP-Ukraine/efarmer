# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).


import requests
from datetime import datetime, timedelta, date

from odoo import fields, models, _
from odoo.exceptions import ValidationError

PROJECT_KEY = "shortName"


class YoutrackIntegration(models.Model):
    _name = "youtrack.integration"
    _description = "YouTrack Integration"

    def _get_api_method(self):
        api_methods = [
            method
            for method in dir(self)
            if method.startswith("youtrackIntegrationApi")
            and callable(getattr(self, method))
        ]
        return [(x, x.replace("youtrackIntegrationApi", "")) for x in api_methods]

    api_method = fields.Selection(_get_api_method, string="API Method")

    name = fields.Char(
        string="Name",
    )

    api_key = fields.Char(
        string="Token",
    )

    api_key_attr = fields.Char(
        string="Token Attribute",
    )

    is_active = fields.Boolean(
        string="Active",
    )

    endpoint = fields.Char(
        string="Endpoint",
        required=True,
    )

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
    )

    project_code = fields.Char()

    date_from = fields.Date(
        string="Start Date",
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
            "Authorization": "{} {}".format(self.api_key_attr, self.api_key),
            "Accept": "application/json",
        }

        if self.endpoint.endswith("/"):
            self.endpoint = self.endpoint[:-1]

        request_url = "{}/{}".format(self.endpoint, uri)
        resp = requests.get(request_url, headers=headers)

        if resp.status_code != 200:
            resp.raise_for_status()

        json_response = resp.json()

        return json_response

    def _filter_project_response(self, ext_projects):
        res = [
            project
            for project in ext_projects
            if project[PROJECT_KEY] == self.project_code
        ]
        return res

    def _get_object(self, model, domain, limit=None, check_unique=False):
        company_dependent_models = [
            "account.analytic.line",
            "project.project",
            "project.task",
            "account.asset",
            "hr.employee",
        ]
        if model in company_dependent_models:
            domain += [("company_id", "=", self.company_id.id)]
            self = self.with_company(self.company_id)
        obj = self.env[model].search(domain, limit=limit)
        if check_unique:
            self.__check_unique(obj)
        return obj

    def __check_unique(self, object):
        if len(object) > 1:
            raise ValidationError(
                _(
                    'There are more than one objects of model {} with the same name "{}"!'
                ).format(object[0]._name, object[0].name)
            )
        return True

    def _create_object(self, model, vals):
        obj = self.env[model].create(vals)
        return obj

    def _get_ts_to_create(self, ext_ts):
        exist_ts = self._get_object(
            "account.analytic.line", [("youtrack_id", "!=", False)]
        )
        exist_ts_ext_ids = exist_ts.mapped("youtrack_id")
        exist_projects = self._get_object(
            "project.project", [("project_code", "!=", False)]
        )
        exist_project_codes = exist_projects.mapped("project_code")

        ts_to_create = [
            ts
            for ts in ext_ts
            if ts["id"] not in exist_ts_ext_ids
            and ts["issue"]["project"]["shortName"] in exist_project_codes
        ]
        return ts_to_create

    def _get_object_by_name(self, model, custom_data):
        domain = [("name", "=", custom_data["name"])]
        obj = self._get_object(model, domain, check_unique=True)

        if obj and not obj.youtrack_id:
            obj.youtrack_id = custom_data["id"]

        if not obj:
            vals = {
                "name": custom_data["name"] or "",
                "youtrack_id": custom_data["id"],
            }
            obj = self._create_object(model, vals)
        return obj

    def _get_account_asset(self, custom_data):
        domain = [
            ("name", "=", custom_data["name"]),
            ("active", "=", True),
        ]
        obj = self._get_object("account.asset", domain, check_unique=True)
        if not obj:
            vals = {
                "name": custom_data["name"] or "",
                "youtrack_id": custom_data["id"],
                # 'type': 'purchase',
                "company_id": self.company_id.id,
            }
            obj = self._create_object("account.asset", vals)
        return obj

    def _get_api_integration(self, integration_id):
        if not integration_id:
            raise ValidationError(_("You need to set parameter integration_id."))
        integration = self.browse(integration_id)
        if not integration.is_active:
            raise ValidationError(_("No active YouTrack Integration found!"))
        return integration

    def __minutes_to_hours(self, minutes):
        hours = float(minutes // 60 + minutes % 60 / 60)
        return hours

    def __get_api_customs_values(self, vals):
        CUSTOM_FIELDS_MAP = {
            "Estimation": ("allocated_hours", None),
            "Type": ("issue_type_id", "youtrack.issue.type"),
            "Product version": ("product_version_id", "youtrack.product.version"),
            "Name PL": ("name_pl", None),
            "Product": ("asset_id", None),
        }

        custom_values = {}
        for field in vals["customFields"]:
            field_name = field.get("name")
            if field_name in CUSTOM_FIELDS_MAP:
                custom_data = field["value"]
                odoo_field, model = CUSTOM_FIELDS_MAP.get(field_name)
                if not model:
                    custom_values[odoo_field] = custom_data
                else:
                    custom_values[odoo_field] = (
                        self._get_object_by_name(model, custom_data).id
                        if custom_data
                        else None
                    )

        if custom_values.get("allocated_hours", False):
            allocated_hours = self.__minutes_to_hours(
                custom_values["allocated_hours"]["minutes"]
            )
            custom_values["allocated_hours"] = allocated_hours

        if custom_values.get("asset_id", False):
            custom_values["asset_id"] = self._get_account_asset(
                custom_values["asset_id"]
            ).id

        if custom_values.get("name_pl", False):
            custom_values["name_pl"] = custom_values["name_pl"]["text"]

        return custom_values

    def _get_employees_data(self, ext_empls):
        update_data = {}
        # search emails of employees case-insensitively in the system
        empls = self._get_object(
            "hr.employee",
            [("work_email", "!=", False), ("active", "in", [True, False])],
        )
        empls_emails = list(map(lambda x: x.lower(), empls.mapped("work_email")))
        # define create list of YouTrack employees which have
        # email and don't exist in Odoo
        empls_to_create = [
            empl
            for empl in ext_empls
            if empl["email"] and empl["email"].lower() not in empls_emails
        ]

        # check if there are employees in Odoo without youtrack_id
        # and prepare data for updating them
        empls_no_ext_ids = empls.filtered(lambda x: not x.youtrack_id)
        if empls_no_ext_ids:
            empls_no_ext_ids = {empl.work_email: empl for empl in empls_no_ext_ids}
            update_data = {
                empl["id"]: empls_no_ext_ids.get(empl["email"])
                for empl in ext_empls
                if empl["email"] in empls_no_ext_ids
            }
        return empls_to_create, update_data

    def __timestamp_to_date(self, timestamp):
        if len(str(timestamp)) == 13:
            res = date.fromtimestamp(timestamp / 1000)
        elif len(str(timestamp)) == 15:
            res = date.fromtimestamp(timestamp / 100000)
        return res

    def _create_project(self, vals):
        self.env["project.project"].create(
            {
                "name": vals.get("name", ""),
                "project_code": vals.get(PROJECT_KEY, ""),
                "youtrack_id": vals.get("id", ""),
                "company_id": self.company_id.id,
            }
        )
        return True

    def _create_task(self, vals):
        project = self._get_object(
            "project.project",
            [("project_code", "=", vals["project"]["shortName"])],
            check_unique=True,
        )
        custom_values = self.__get_api_customs_values(vals)

        new_vals = {
            "name": vals.get("summary") or "",
            "project_id": project.id or None,
            "youtrack_id": vals.get("id") or "",
            "task_code": vals.get("idReadable") or "",
            "allocated_hours": custom_values.get("allocated_hours"),
            "product_version_id": custom_values.get("product_version_id"),
            "issue_type_id": custom_values.get("issue_type_id"),
            "name_pl": custom_values.get("name_pl"),
            "company_id": self.company_id.id,
        }
        if custom_values.get("asset_id"):
            new_vals.update(
                {
                    "is_epic": True,
                    "asset_id": custom_values.get("asset_id"),
                }
            )
        new_task = self.env["project.task"].create(new_vals)
        return new_task

    def _create_ts(self, vals, employee):
        task = self._get_object(
            "project.task",
            [("youtrack_id", "=", vals["issue"]["id"])],
            check_unique=True,
        )

        if vals.get("type"):
            work_type_id = self._get_object_by_name(
                "youtrack.work.type", vals["type"]
            ).id
        else:
            work_type_id = self._get_object(
                "youtrack.work.type", [("is_default", "=", True)]
            ).id

        date = self.__timestamp_to_date(vals.get("date"))

        self.env["account.analytic.line"].create(
            {
                "youtrack_id": vals.get("id"),
                "name": vals.get("text", ""),
                "date": date,
                "unit_amount": self.__minutes_to_hours(vals["duration"]["minutes"]),
                "employee_id": employee.id,
                "work_type_id": work_type_id,
                "project_id": task.project_id.id if task.project_id else None,
                "task_id": task.id if task else None,
                "company_id": self.company_id.id,
            }
        )
        return True

    def _create_employee(self, vals):
        new_vals = {
            "name": vals.get("fullName", ""),
            "work_email": vals.get("email", ""),
            "youtrack_id": vals.get("id", ""),
            "company_id": self.company_id.id,
        }
        if vals.get("banned"):
            new_vals.update(
                {
                    "active": False,
                }
            )
        self.env["hr.employee"].create(new_vals)
        return True

    def _create_epic_links(self):
        epic_tasks = self._get_object("project.task", [("is_epic", "=", True)])
        for epic in epic_tasks:
            childs = self._get_object(
                "project.task", [("id", "child_of", epic.child_ids.ids)]
            )
            for child in childs:
                child.epic_id = epic.id
                child.product_version_id = (
                    epic.product_version_id.id if epic.product_version_id else None
                )
                child.asset_id = epic.asset_id.id if epic.asset_id else None
                child.name_pl = epic.name_pl if epic.name_pl else None

    def _validate_project_request(self):
        if not self.project_code:
            raise ValidationError(
                _("You need to set Project Code for importing Project.")
            )

        if self._get_object(
            "project.project", [("project_code", "=", self.project_code)], limit=1
        ):
            raise ValidationError(
                _('Project with code "{}" already exists in Odoo.').format(
                    self.project_code
                )
            )

    def _validate_work_items_request(self):
        if not self.date_from:
            raise ValidationError(
                _("You need to set Start Date for importing Work Items.")
            )

    def api_get_project(self, project_code):
        get_project_url = (
            "admin/projects?fields=name,shortName,"
            "id&$top=100000&query={}".format(project_code)
        )
        ext_project = self._send_youtrack_request(get_project_url) or []
        if ext_project:
            # we can't receive exact response with such request,
            # and we need to avoid creation of more than one project
            project_to_create = self._filter_project_response(ext_project)
            if project_to_create:
                self._create_project(project_to_create[0])

    def api_get_employees(self):
        get_employee_url = "users?fields=id,fullName,email,banned&&$top=100000"
        ext_employees = self._send_youtrack_request(get_employee_url) or []
        if ext_employees:
            # create employee if employee with imported email doesn't exist
            # in Odoo, otherwise write youtrack_id if it's empty
            empls_to_create, update_data = self._get_employees_data(ext_employees)

            if empls_to_create:
                for employee in empls_to_create:
                    self._create_employee(employee)

            if update_data:
                for youtrack_id, employee in update_data.items():
                    employee.youtrack_id = youtrack_id

    def api_get_task(self, task_ext_id, child=None):
        """
        Check if task exists in Odoo, otherwise get it from
        integration and repeat this operation recursively
        as long as the task has a parent.
        After each recursive execution create link between parent
        and child tasks.
        """
        task = self._get_object(
            "project.task", [("youtrack_id", "=", task_ext_id)], check_unique=True
        )
        if task:
            if child:
                child.parent_id = task.id
            return True

        get_tasks_url = (
            "issues/{}?fields=id,idReadable,summary,project(id,shortName),"
            "parent(issues(id,project(id,shortName))),customFields(name,"
            "value(id,text,name,minutes))&customFields=type&"
            "customFields=Estimation&customFields=Product version&"
            "customFields=Product&customFields=Name PL&$top=1".format(task_ext_id)
        )
        ext_task = self._send_youtrack_request(get_tasks_url) or []
        if ext_task:
            task = self._create_task(ext_task)
            if child:
                child.parent_id = task.id

            parent_task = ext_task["parent"]["issues"]
            # get and create parent task recursively
            if parent_task:
                parent_id = parent_task[0]["id"]
                parent_project_code = parent_task[0]["project"]["shortName"]
                parent_project = self._get_object(
                    "project.project",
                    [("project_code", "=", parent_project_code)],
                    check_unique=True,
                )
                # create task if project exists in Odoo
                if parent_project:
                    self.api_get_task(parent_id, child=task)
            return True

    def api_get_work_items(self, start):
        # import work items (timesheets) for all existing employees with youtrack_id
        employees = self._get_object("hr.employee", [("youtrack_id", "!=", False)])
        for employee in employees:
            get_ts_url = (
                "workItems?fields=date,duration(minutes),author(id),text,"
                "type,id,type(id,name),issue(id,project(id,shortName))&startDate={}"
                "&author={}&$top=100000".format(start, employee.youtrack_id)
            )
            ext_ts = self._send_youtrack_request(get_ts_url) or []
            if ext_ts:
                # filter out existing ts and ts with project, that doesn't exist in Odoo
                ts_to_create = self._get_ts_to_create(ext_ts)
                for ts in ts_to_create:
                    self.api_get_task(ts["issue"]["id"])
                    self._create_ts(ts, employee)
        # create links for all childs to its epic task
        self._create_epic_links()

    def youtrackIntegrationApiGetProject(self):
        self._validate_project_request()
        self.with_delay().api_get_project(self.project_code)

    def youtrackIntegrationApiGetWorkItems(self, integration_id=None, period=None):
        if self.env.context.get("with_cron", False):
            self = self._get_api_integration(integration_id)
            start = (datetime.today() - timedelta(days=period)).strftime("%Y-%m-%d")
        else:
            self._validate_work_items_request()
            start = self.date_from.strftime("%Y-%m-%d")

        self.with_delay().api_get_work_items(start)

    def youtrackIntegrationApiGetEmployees(self):
        self.with_delay().api_get_employees()

    # def _cron_import_work_items(self):
    #     self.with_context(with_cron=True).youtrackIntegrationApiGetWorkItems(integration_id=None, period=30)
