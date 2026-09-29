# See LICENSE file for full copyright and licensing details.

import logging

from odoo import models


_logger = logging.getLogger(__name__)


class Base(models.AbstractModel):
    _inherit = 'base'

    def get_formview_action_log(self):
        return self.get_formview_action()

    def is_module_installed(self, name):
        module = self.sudo().env.ref(f'base.module_{name}', raise_if_not_found=False)
        return (module.state == 'installed') if module else False

    def _get_field_string(self, name):
        if name in self._fields:
            return self._fields[name].string
        return name

    def display_integration_notification(
        self, message, title=None, ttype='success', sticky=False, next_action=None, reload=False,
    ):
        """Build an `ir.actions.client` `display_notification` action for returning from action methods.

        `next_action` maps to Odoo's native `params.next`, which the web client runs right after the
        notification is shown, so multiple actions can be chained from a single method. Defaults to
        closing the current window/dialog; pass `next_action=False` to chain nothing. `reload=True`
        chains a `soft_reload` client action instead, refreshing the current view rather than closing it.
        """
        if next_action is None:
            next_action = {'type': 'ir.actions.client', 'tag': 'soft_reload'} if reload \
                else {'type': 'ir.actions.act_window_close'}

        params = {
            'message': message,
            'type': ttype,
            'sticky': sticky,
        }
        if title:
            params['title'] = title
        if next_action:
            params['next'] = next_action

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': params,
        }
