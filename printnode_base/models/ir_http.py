# Copyright 2021 VentorTech OU
# See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.http import request


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    def _get_active_company(self):
        # Since in certain cases Odoo does not always provide the active company
        # in the env, it is necessary to get it from cookies.
        cids = request.cookies.get('cids')
        if not cids:
            return self.env.company

        first_id = str(cids).replace('-', ',').split(',')[0].strip()
        if not first_id.isdigit():
            return None

        return request.env['res.company'].browse(int(first_id)).exists()

    def session_info(self):
        # Since Odoo 14, session_info() returns User->Default Company, not General Company.
        # This influence the "Print" and "Downloads" interface menus. If the module's
        # Direct Print settings are different between General Company and
        # User -> Default Company, then the display of the "Print" and "Downloads"
        # menus may not be correct.
        res = super(IrHttp, self).session_info()

        dpc_company_enabled = False
        dpc_user_enabled = False

        active_company = self._get_active_company()
        if active_company and active_company.printnode_enabled \
                and self.env.user.has_group("printnode_base.printnode_security_group_user"):
            dpc_company_enabled = True

            if self.env.user.printnode_enabled:
                dpc_user_enabled = True

        res.update({
            'dpc_company_enabled': dpc_company_enabled,
            'dpc_user_enabled': dpc_user_enabled,
        })

        return res
