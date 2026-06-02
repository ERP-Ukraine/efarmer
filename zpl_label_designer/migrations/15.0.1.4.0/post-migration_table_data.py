# See LICENSE file for full copyright and licensing details.
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    # The 'zld_allowed_models' Many2many used to rely on the auto-generated
    # relation table name. For comodel 'ir.model' (table 'ir_model') and model
    # 'res.company' (table 'res_company'), Odoo sorts the two table names and
    # builds '<a>_<b>_rel', i.e. 'ir_model_res_company_rel'. The field now uses
    # an explicit relation ('ir_model_res_company_zld_rel'). Copy any existing
    # data from the old table into the new one so company-to-model links are
    # preserved. Guard on table existence to stay idempotent and safe.
    cr.execute("""
        SELECT 1
        FROM information_schema.tables
        WHERE table_name = 'ir_model_res_company_rel';
    """)
    old_table_exists = cr.fetchone()

    cr.execute("""
        SELECT 1
        FROM information_schema.tables
        WHERE table_name = 'ir_model_res_company_zld_rel';
    """)
    new_table_exists = cr.fetchone()

    if old_table_exists and new_table_exists:
        cr.execute("""
            INSERT INTO ir_model_res_company_zld_rel (company_id, model_id)
            SELECT res_company_id, ir_model_id
            FROM ir_model_res_company_rel
            ON CONFLICT DO NOTHING;
        """)
    else:
        env = api.Environment(cr, SUPERUSER_ID, {})
        company_model = env['res.company']
        company_model._set_default_zld_allowed_models()
