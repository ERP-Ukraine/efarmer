# See LICENSE file for full copyright and licensing details.
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    cr.execute("""
        SELECT 1
        FROM information_schema.tables
        WHERE table_name = 'ir_model_res_company_rel';
    """)
    result = cr.fetchone()

    if result is not None:
        cr.execute("""
            INSERT INTO ir_model_res_company_zld_rel (company_id, model_id)
            SELECT res_company_id, ir_model_id
            FROM ir_model_res_company_rel;
        """)
    else:
        env = api.Environment(cr, SUPERUSER_ID, {})
        company_model = env['res.company']
        company_model._set_default_zld_allowed_models()
