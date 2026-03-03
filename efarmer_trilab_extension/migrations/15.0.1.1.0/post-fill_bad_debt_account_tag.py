# Copyright 2025 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, dict())
    env.cr.execute(f"""
INSERT INTO account_account_tag_account_move_line_rel (account_move_line_id , account_account_tag_id)
select a2.account_move_line_id, {env.ref('efarmer_trilab_extension.pl_jpk_K_46_K_47').id}
from account_account_tag_account_move_line_rel a2
join account_move_line a3
    on a3.id = a2.account_move_line_id
where
    a3.tax_line_id = {env.ref('l10n_pl.3_vz_kraj_23').id}
    and a2.account_account_tag_id = {env.ref('trilab_jpk_vat.pl_jpk_K_46').id};
    """)
