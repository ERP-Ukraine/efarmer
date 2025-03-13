
# Copyright 2025 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).


def migrate(cr, version):

    cr.execute("ALTER TABLE sale_order ADD COLUMN IF NOT EXISTS efarmer_confirm_date date;")
    cr.execute("""
WITH status_priority AS (
    SELECT 'To Confirm' AS status, 1 AS priority UNION ALL
    SELECT 'Sales Order', 2 UNION ALL
    SELECT 'Locked', 3
),
latest_dates AS (
    SELECT so.id, coalesce(mtv.write_date, sp.create_date)::date AS new_date
    FROM sale_order so
    left JOIN (
        SELECT DISTINCT ON (sp.sale_id) sp.sale_id, sp.create_date FROM stock_picking sp
        order by sp.sale_id, sp.create_date asc
    ) AS sp ON so.id = sp.sale_id
    LEFT JOIN (
        SELECT DISTINCT ON (mm.res_id) mm.res_id, sp.priority, mtv.write_date
        FROM mail_tracking_value mtv
        JOIN mail_message mm ON mm.id = mtv.mail_message_id
        JOIN status_priority sp ON mtv.new_value_char = sp.status
        WHERE field IN (
            SELECT imf.id FROM ir_model_fields imf
            WHERE imf.model='sale.order' AND imf.name='state'
        )
        ORDER BY mm.res_id, sp.priority, mtv.write_date DESC
    ) AS mtv ON mtv.res_id = so.id
    WHERE
        so.state IN ('to_confirm', 'sale', 'done')
        AND coalesce(mtv.write_date, sp.create_date) IS NOT NULL
)
UPDATE sale_order so
SET efarmer_confirm_date = ld.new_date
FROM latest_dates ld
WHERE so.id = ld.id;
    """)
