# See LICENSE file for full copyright and licensing details.

from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    env.cr.execute(
        """
        UPDATE integration_sale_order_sub_status_external
        SET validate_order = true
        """
    )
