# Copyright (C) 2025 ForgeFlow S.L.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html)

from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})

    # Only fill when posted_uid is empty
    cr.execute("""
        UPDATE account_move
           SET posted_uid = write_uid
         WHERE posted_uid IS NULL
           AND state = 'posted'
    """)
