# See LICENSE file for full copyright and licensing details.


def migrate(cr, version):
    """One-off correction for installations that already ran the buggy
    19.0.2.2.0 pre-migrate-order-automation.py: it classified a pipeline as
    'running' whenever any task was 'in_process' or 'todo', while
    _compute_pipeline_status (and IntegrationWorkflowPipeline.status) treats a
    pipeline with no 'done'/'in_process' task at all as 'none' (Pending), not
    'running'. Freshly-created pipelines (tasks in 'todo' + 'skip') were
    therefore mislabeled 'running' instead of 'Pending'.

    Re-applies the corrected CASE (mirrors status priority: cancelled >
    failed > skipped > done > none > running) to every input file linked to a
    pipeline. Idempotent, safe to run more than once. Input files without a
    pipeline were not affected by the bug and are untouched.
    """
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
