# See LICENSE file for full copyright and licensing details.

import traceback

from odoo import models, fields, _


class IntegrationAuthAbstract(models.AbstractModel):
    _name = 'integration.auth.abstract'
    _description = 'Integration Authentication Abstract'

    integration_id = fields.Many2one(
        comodel_name='sale.integration',
        string='Integration',
    )

    url = fields.Char(
        string='Store URL',
    )

    key = fields.Char(
        string='Token',
    )

    access_granted = fields.Boolean(
        string='Access Granted',
    )

    error_message = fields.Text(
        string='Error Message',
        readonly=True,
    )

    error_traceback = fields.Text(
        string='Error Traceback',
        readonly=True,
    )

    def test_connection(self):
        self.ensure_one()
        # Clear any previous errors
        self.write({
            'error_message': False,
            'error_traceback': False,
        })

        self.env.registry.clear_cache()

        try:
            self._build_and_test_client_from_wizard()

            self.write({
                'access_granted': True,
            })
            self.save_credentials()

            message = _('Connection test successful! Your connection to the e-commerce store is working correctly.')
            return self._raise_client_notification('success', message)
        except Exception as e:
            # Store error information
            error_msg = str(e)
            error_tb = traceback.format_exc()

            self.write({
                'error_message': error_msg,
                'error_traceback': error_tb,
            })

            # Return to the same form to show the error
            return self.open_form()

    def save_credentials(self):
        raise NotImplementedError

    def reset_credentials(self):
        self.ensure_one()

        self.access_granted = False
        self.integration_id.set_settings_value('access_granted', 'False')

        return self.open_form()

    def open_form(self):
        self.ensure_one()

        action = self.integration_id._get_integration_auth_action(add_default_context=False)
        action['res_id'] = self.id

        return action

    def close_form(self):
        return {
            'type': 'ir.actions.act_window_close',
        }

    def _build_and_test_client_from_wizard(self):
        raise NotImplementedError

    def connect_to_ecommerce_store(self):
        """
        Generic method to handle base authentication with error handling.
        This method should be called by all request_for_*_base_auth methods.
        """
        self.ensure_one()
        # Clear any previous errors
        self.write({
            'error_message': False,
            'error_traceback': False,
        })

        try:
            self.test_connection()
            return self.open_form()
        except Exception as e:
            # Store error information
            error_msg = str(e)
            error_tb = traceback.format_exc()

            self.write({
                'error_message': error_msg,
                'error_traceback': error_tb,
            })

            # Return to the same form to show the error
            return self.open_form()

    def check_access_permissions(self):
        """
        Generic method to handle authorization (checking access scopes/permissions).
        Integrations that don't support authorization can skip implementing
        _build_scope_lines() and open_form_authorization().
        """
        self.ensure_one()
        self._build_scope_lines()
        return self.open_form_authorization()

    def continue_to_configuration(self):
        """
        Generic method to continue to the connection configuration.
        It means open the `configuration.wizard` form.
        """
        self.ensure_one()

        integration = self.integration_id

        # Cache invalidating provides the ability to create a configuration-wizard from the scratch
        integration.invalidate_integration_cache()

        return integration.action_run_configuration_wizard()

    def _build_scope_lines(self):
        """
        Build scope lines for authorization check.
        Should be implemented by integrations that support authorization.
        """
        raise NotImplementedError("This integration does not support authorization")

    def open_form_authorization(self):
        """
        Open the authorization form.
        Should be implemented by integrations that support authorization.
        """
        raise NotImplementedError("This integration does not support authorization")

    def _raise_client_notification(self, ttype: str, message: str):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': message,
                'type': ttype,
                'sticky': False,
            }
        }
