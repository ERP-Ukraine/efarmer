# Copyright 2022 VentorTech OU
# See LICENSE file for full copyright and licensing details.


def migrate(cr, version):
    cr.execute("""
        DELETE FROM "ir_model_fields_selection" WHERE "field_id" IN (
            SELECT "id"
            FROM "ir_model_fields"
            WHERE model_id IN (
                SELECT "id"
                FROM "ir_model"
                WHERE "model" = 'zld.label'
            )
            AND name = 'dpi'
        )
    """)
    cr.execute('ALTER TABLE "zld_label" ALTER COLUMN "dpi" TYPE integer USING (dpi::integer)')
