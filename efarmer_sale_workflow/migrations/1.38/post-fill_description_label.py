# Copyright 2025 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, dict())
    env.cr.execute("""
select
    it.res_id,
    jsonb_object_agg(it.lang, it.value) as data
from ir_translation it
where
    it.name = 'product.template,description_label'
    and it.type = 'model'
    and it.res_id is not null
    and it.state = 'translated'
group by it.res_id;
    """)

    for res_id, data in env.cr.fetchall():
        tmpl_id = env['product.template'].browse(res_id)
        if data:
            for lang, value in data.items():
                for product_id in tmpl_id.product_variant_ids:
                    if not product_id.with_context(lang=lang).description_label:
                        product_id.with_context(lang=lang).write({"description_label": value})
