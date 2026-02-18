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
