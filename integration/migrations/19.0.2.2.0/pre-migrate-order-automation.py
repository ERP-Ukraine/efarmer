# See LICENSE file for full copyright and licensing details.


def migrate(cr, version):
    """Back-fill the new stored pipeline_status on sale.integration.input.file via
    set-based SQL, so Odoo's _auto_init finds the column already present and skips
    the per-row recompute over the whole (multi-million row) table.

    Mirrors _compute_pipeline_status priority: cancelled > failed > skipped >
    done > none > running.
    """
    # 1) Create the column up-front so the ORM does not schedule a mass recompute.
    cr.execute("""
        ALTER TABLE sale_integration_input_file
            ADD COLUMN IF NOT EXISTS pipeline_status VARCHAR;
    """)

    # 2) One set-based pass: for each input file pick its pipeline (smallest id,
    #    matching pipeline_ids[:1]) and aggregate that pipeline's task states.
    cr.execute("""
        WITH pl AS (
            SELECT DISTINCT ON (p.input_file_id)
                   p.input_file_id AS sif_id,
                   p.id            AS pipeline_id
            FROM integration_workflow_pipeline p
            WHERE p.input_file_id IS NOT NULL
            ORDER BY p.input_file_id, p.id
        ),
        agg AS (
            SELECT pl.sif_id,
                   COALESCE(bool_or(t.state = 'failed'), FALSE)                AS has_failed,
                   COALESCE(bool_and(t.state = 'skip'), TRUE)                  AS all_skipped,
                   COALESCE(bool_and(t.state IN ('skip', 'done')), TRUE)       AS all_done,
                   COALESCE(bool_or(t.state IN ('done', 'in_process')), FALSE) AS has_progress
            FROM pl
            LEFT JOIN integration_workflow_pipeline_line t ON t.pipeline_id = pl.pipeline_id
            GROUP BY pl.sif_id
        )
        UPDATE sale_integration_input_file sif
        SET pipeline_status = CASE
                WHEN sif.state = 'cancelled' THEN 'cancelled'
                WHEN a.has_failed            THEN 'failed'
                WHEN a.all_skipped           THEN 'skipped'
                WHEN a.all_done              THEN 'done'
                WHEN NOT a.has_progress      THEN 'none'
                ELSE 'running'
            END
        FROM agg a
        WHERE a.sif_id = sif.id;
    """)

    # 3) Input files with no pipeline at all: cancelled (terminal) or none.
    cr.execute("""
        UPDATE sale_integration_input_file
        SET pipeline_status = CASE WHEN state = 'cancelled' THEN 'cancelled' ELSE 'none' END
        WHERE pipeline_status IS NULL;
    """)

    # 4) Back-fill the new per-status `apply_advance_payment` step from the old
    #    integration-level `create_advance_payments` checkbox, matching the old
    #    `_integration_post_order_confirm` behavior (only ran when `validate_order`
    #    was already enabled).
    cr.execute("""
        ALTER TABLE integration_sale_order_sub_status_external
            ADD COLUMN IF NOT EXISTS apply_advance_payment BOOLEAN;
    """)

    cr.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'sale_integration' AND column_name = 'create_advance_payments'
    """)
    if cr.fetchone():
        cr.execute("""
            UPDATE integration_sale_order_sub_status_external AS sub
            SET apply_advance_payment = TRUE
            FROM sale_integration AS si
            WHERE sub.integration_id = si.id
              AND si.create_advance_payments IS TRUE
              AND sub.validate_order IS TRUE
              AND sub.register_payment IS NOT TRUE
              AND sub.apply_advance_payment IS NOT TRUE
        """)
