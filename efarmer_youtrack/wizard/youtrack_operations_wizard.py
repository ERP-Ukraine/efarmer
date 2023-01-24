from odoo import fields, models, _


class YoutrackOperationsWizard(models.TransientModel):
    _name = 'youtrack.operations.wizard'
    _description = 'YouTrack Operations Wizard'

    import_all_projects = fields.Boolean(
        string='Import All Projects',
    )

    import_project_by_code = fields.Boolean(
        string='Import Project By Code',
    )

    project_code = fields.Char()

    import_all_tasks = fields.Boolean(
        string='Import All Task',
    )

    import_all_employees = fields.Boolean(
        string='Import All Employees',
    )

    import_employee_by_email = fields.Boolean(
        string='Import Employee By Email',
    )

    email = fields.Char()

    import_all_timesheets = fields.Boolean(
        string='Import All Timesheets',
    )

    import_timesheet_for_period = fields.Boolean(
        string='Import Timesheets For A Period',
    )

    date_from = fields.Datetime(
        string='From',
    )

    date_to = fields.Datetime(
        string='To',
    )

    def run_integration(self):
        pass
