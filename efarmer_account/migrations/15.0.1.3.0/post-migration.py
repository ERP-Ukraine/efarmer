# Copyright (C) 2025 ForgeFlow S.L.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html)

from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})

    # posted_uid on account.move
    cr.execute("""
        UPDATE account_move
           SET posted_uid = write_uid
         WHERE posted_uid IS NULL
           AND state = 'posted'
    """)

    cr.execute("""
        UPDATE account_move_line aml
        SET posted_uid = aml.write_uid
        FROM account_move am
        WHERE aml.move_id = am.id
          AND aml.posted_uid IS NULL
          AND am.state = 'posted'
    """)
