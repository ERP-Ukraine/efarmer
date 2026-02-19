# See LICENSE file for full copyright and licensing details.

from odoo import models


class Base(models.AbstractModel):
    _inherit = 'base'

    def is_module_installed(self, name):
        module = self.sudo().env.ref(f'base.module_{name}', raise_if_not_found=False)
        return (module.state == 'installed') if module else False
