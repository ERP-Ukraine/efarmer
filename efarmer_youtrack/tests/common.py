# Copyright 2023 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from unittest.mock import patch
from odoo.tests import common


API_PROJECT_RESPONSE = [
    {
        'shortName': 'TEST',
        'name': 'Test Project',
        'id': '1-1',
        '$type': 'Project',
    }
]

API_EMPLOYEE_RESPONSE = [
    {
        'email': 'test@user_1.com',
        'fullName': 'Test User 1',
        'id': '11-11',
        'banned': False,
        '$type': 'User',
    },
    {
        'email': 'test@user_2.com',
        'fullName': 'Test User 2',
        'id': '22-22',
        'banned': True,
        '$type': 'User',
    },
    {
        'email': None,
        'fullName': 'Test User 3',
        'id': '33-33',
        'banned': False,
        '$type': 'User',
    }
]

API_WORK_ITEM_RESPONSE = [
    {
        'date': 1670198400000,
        'duration': {
            'minutes': 62,
            '$type': 'DurationValue'
        },
        'issue': {
            'project': {
                'id': '1-1',
                'shortName': 'TEST',
                '$type': 'Project'
            },
            'id': '99-99',
            '$type': 'Issue'
        },
        'text': 'The work item automatically added by the timer.',
        'type': {
            'name': 'Test Work Type',
            'id': '8-8',
            '$type': 'WorkItemType',
        },
        'author': {
            'id': '11-11',
            '$type': 'User'
        },
        'id': '101-25445',
        '$type': 'IssueWorkItem'
    }
]

API_TASK_RESPONSE = {
    'idReadable': 'Test Task',
    'summary': 'Summary of Test Task ',
    'project': {
            'id': '1-1',
            'shortName': 'TEST',
            '$type': 'Project'
            },
    'customFields': [
                        {
                            'value': {
                                'name': 'User Story',
                                'id': '53-35',
                                '$type': 'EnumBundleElement'
                            },
                            'name': 'Type',
                            '$type': 'SingleEnumIssueCustomField'
                        },
                        {
                            'value': {
                                'minutes': 660,
                                'id': 'P1DT3H',
                                '$type': 'PeriodValue'
                            },
                            'name': 'Estimation',
                            '$type': 'PeriodIssueCustomField'
                        },
                        {
                            'value': 'Name in Polish',
                            'name': 'Name PL',
                            '$type': 'TextIssueCustomField'
                        },
                        {
                            'value': None,
                            'name': 'Product',
                            '$type': 'SingleEnumIssueCustomField'
                        },
                        {
                            'value': None,
                            'name': 'Product version',
                            '$type': 'SingleVersionIssueCustomField'
                        },
                    ],
    'parent': {
            'issues': [
                        {
                            'project': {
                                    'id': '1-1',
                                    'shortName': 'TEST',
                                    '$type': 'Project'
                                    },
                            'id': '93-28945',
                            '$type': 'Issue',
                        }
                    ],
            '$type': 'IssueLink'
            },
    'id': '99-999',
    '$type': 'Issue'
}

API_PARENT_TASK_RESPONSE = {
    'idReadable': 'Parent Test Task',
    'summary': 'Summary of Parent Test Task ',
    'project': {
            'id': '1-1',
            'shortName': 'TEST',
            '$type': 'Project'
            },
    'customFields': [
                        {
                            'value': {
                                'name': 'User Story',
                                'id': '54-36',
                                '$type': 'EnumBundleElement'
                            },
                            'name': 'Type',
                            '$type': 'SingleEnumIssueCustomField'
                        },
                        {
                            'value': {
                                'minutes': 550,
                                'id': 'P1DT',
                                '$type': 'PeriodValue'
                            },
                            'name': 'Estimation',
                            '$type': 'PeriodIssueCustomField'
                        },
                        {
                            'value': 'Name in Polish',
                            'name': 'Name PL',
                            '$type': 'TextIssueCustomField'
                        },
                        {
                            'value': {
                                'name': 'Test Product',
                                'id': '53-488',
                                '$type': 'EnumBundleElement'
                            },
                            'name': 'Product',
                            '$type': 'SingleEnumIssueCustomField'
                        },
                        {
                            'value': {
                                'name': 'Test Product Version',
                                'id': '103-1058',
                                '$type': 'VersionBundleElement'
                            },
                            'name': 'Product version',
                            '$type': 'SingleVersionIssueCustomField'
                        },
                    ],
    'parent': {
        'issues': [],
        '$type': 'IssueLink'
    },
    'id': '93-28945',
    '$type': 'Issue'
}


class TestYoutrackIntegrationCommon(common.TransactionCase):

    def _create_patch_object(self, target, attribute):
        """
        This method makes it easier to work with unittest.mock.patch()<.object()> functions.
        It avoids extra nested indentation as when using patch() with the "with" context manager.
        """

        patcher = patch.object(target, attribute)
        thing = patcher.start()
        self.addCleanup(patcher.stop)
        return thing
