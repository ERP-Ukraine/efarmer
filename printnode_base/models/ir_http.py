# Copyright 2021 VentorTech OU
# See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.http import request


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    def _get_active_company(self):
        # Since in certain cases Odoo does not always provide the active company
        # in the env, it is necessary to get it from cookies.

        # VENSUP-22365: on Odoo.sh, for some users during login/session initialization,
        # the `cids` cookie may be missing, malformed, or contain a company that is not
        # available to the current user. In this case Direct Print must not break the
        # login flow, so the user's default company is used as a safe fallback.
        #
        # This is an Odoo.sh-specific fix for the issue described in VENSUP-22365.
        default_company = self.env.user.company_id.sudo()

        cids = request.cookies.get('cids')
        if not cids:
            return default_company

        first_id = str(cids).replace('-', ',').split(',')[0].strip()
        if not first_id.isdigit():
            return default_company

        company_id = int(first_id)
        if company_id not in self.env.user._get_company_ids():
            return default_company

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
